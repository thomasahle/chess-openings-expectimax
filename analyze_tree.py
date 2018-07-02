import chess, chess.pgn, chess.uci
import bz2, requests
import collections, heapq
import os.path, pickle
import math, random
import argparse, datetime


archive_url = 'https://database.lichess.org/standard/lichess_db_standard_rated_{year:04d}-{month:02d}.pgn.bz2'

def start_engine(stockfish_path, search_time):
    """
    Spawn a new uci engine from the given path.
    """
    engine = chess.uci.popen_engine(stockfish_path)
    engine.setoption({'Threads': 5})
    info_handler = chess.uci.InfoHandler()
    engine.info_handlers.append(info_handler)
    engine.uci()
    return engine, info_handler, search_time


evals = 0
def evaluate(eih, board):
    """
    Evaluate the board using the given engine.
    Returns the best move as well as the score from the perspective
    of the current player in the range [-1, 1].
    """
    global evals
    evals += 1

    engine, info_handler, search_time = eih
    engine.position(board)
    move, ponder = engine.go(movetime=search_time)
    score = info_handler.info['score'][1]
    if score.cp is not None:
        return move, 2/(1 + 10**(-score.cp/400)) - 1
    if score.mate > 0:
        return move, 1
    return move, -1


def download_games(year, month, max_games):
    """
    Download and parsse lichess games from year, month.
    """
    r = requests.get(archive_url.format(year=year, month=month), stream=True)
    with bz2.open(r.raw, 'rt') as b:
        for _ in range(max_games):
            try:
                game = chess.pgn.read_game(b)
            # read_game is supposed to return None if there are not more games,
            # but sometimes it appears to throw an EOFError instead.
            except EOFError:
                break
            if game is None:
                break
            yield game
            #welo = game.headers['WhiteElo']
            #belo = game.headers['BlackElo']
            #tc = game.headers['TimeControl']


def make_tree(htree, games):
    """
    Add games to a position -> visits counter.
    """
    for i, game in enumerate(games):
        board = game.board()
        if i % 1000 == 0:
            print(i, 'games processed', end='\r')
        for j, move in enumerate(game.main_line()):
            key = hash(board._transposition_key())
            first_visit = not htree[key]
            htree[hash((key, move))] += 1
            htree[key] += 1
            if first_visit:
                break
            board.push(move)


def search(board, engine, etree, htree, tresh):
    """
    Perform expectimax.
    Could also use mcts.
    """
    # Search is always called from the perspective of ourselves

    root_key = hash(board._transposition_key())

    if root_key in etree:
        value = etree[root_key]
        # We could be going in a circle.
        # No reason to break this in the probabilistically correct way
        if value == 'open':
            move, score = evaluate(engine, board)
            etree[root_key] = (move, score)
            return score
        best_move, best_score = value
        return best_score
    else:
        etree[root_key] = 'open'

    if htree[root_key] < tresh:
        move, score = evaluate(engine, board)
        etree[root_key] = (move, score)
        return score

    print(evals, '...', end='\r')

    best_move, best_score = None, -1
    for move in board.legal_moves:
        board.push(move)
        key = hash(board._transposition_key())
        if htree[key] < tresh:
            # After applying our move, evaluate gives the score from
            # the perspective of our opponent, so we negate it.
            # TODO: Should we cache this?
            _, mscore = evaluate(engine, board)
            score = -mscore
        else:
            score = 0
            denom = 0
            for opp_move in board.legal_moves:
                board.push(opp_move)
                val = search(board, engine, etree, htree, tresh)
                board.pop()
                # We use a Laplace smoothing, adding 1 to each move.
                move_cnt = htree[hash((key, opp_move))] + 1
                score += val * move_cnt
                denom += move_cnt
            score /= denom
        board.pop()
        # From our own perspective, we always pick the best move.
        # Expecti-max style.
        if score >= best_score:
            best_move = move
            best_score = score

    etree[root_key] = (best_move, best_score)
    return best_score


def make_pv_tree(htree, etree, n):
    """
    n is the number nodes in the tree
    """
    board = chess.Board()
    move, score = etree[hash(board._transposition_key())]
    subtree = []
    tree = [(score, move, subtree)]
    q = [] # (-logp, p, random, move, board, tree-where-it-should-live)
    board.push(move)
    for pp, move in most_common(board, htree):
        board.push(move)
        heapq.heappush(q, (-math.log(pp), random.random(), pp, move, board.copy(), subtree))
        board.pop()
    board.pop()

    while n != 0 and q:
        # Get and add node from heap
        mlogp, _, p, move, board, subtree = heapq.heappop(q)
        n -= 1
        sub2tree = []
        subtree.append((p, move, sub2tree))
        # Get and add response node
        key = hash(board._transposition_key())
        if key not in etree:
            continue
        move, score = etree[key]
        if move is None:
            continue
        sub3tree = []
        sub2tree.append((score, move, sub3tree))
        # Add response-response nodes to heap
        board.push(move)
        for pp, move in most_common(board, htree):
            board.push(move)
            heapq.heappush(q, (mlogp - math.log(pp), random.random(), pp, move, board.copy(), sub3tree))
            board.pop()
        board.pop()

    return tree


def print_pv_tree(pv_tree, board=None, indent='', has_siblings=False):
    if board is None:
        board = chess.Board()
    for p, move, subtree in pv_tree:
        if board.turn == chess.BLACK:
            print(indent, f'{board.san(move)}: {p:.2f}')
        else:
            print(indent, f'{board.san(move)}. Score: {p:.2f}')
        board.push(move)
        subindent = indent + (' | ' if has_siblings else ' '*3)
        print_pv_tree(subtree, board, subindent, has_siblings=len(subtree) > 1)
        board.pop()


def most_common(board, htree):
    res = []
    total = 0
    for move in board.legal_moves:
        cnt = htree[hash((hash(board._transposition_key()), move))]
        if cnt != 0:
            res.append((cnt, move))
            total += cnt
    res = [(cnt/total, move) for cnt, move in res]
    res.sort(reverse=True, key=lambda ab: ab[0])
    return res


def process_date(year, month, htree, args):
    htree_path = f'htree_{year}_{month}.pkl'
    etree_path = f'etree_{year}_{month}.pkl'
    if os.path.isfile(htree_path):
        print(f'Loading htree from {htree_path}')
        with open(htree_path, 'rb') as f:
            htree_cached = pickle.load(f)
        htree += htree_cached
    else:
        # If we redo htree we also have to redo etree
        if os.path.isfile(etree_path):
            print(f'Removing {etree_path}')
            os.remove(etree_path)
        htree_new = collections.Counter()
        print('Making human tree from download...')
        games = download_games(year, month, args.games)
        make_tree(htree_new, games)
        print() # make_tree uses \r, so we want a free line to keep the last output
        # TODO: Consider trimming the tree by removing all nodes with less
        # visits than the treshold.
        print(f'Saving to {htree_path}...')
        with open(htree_path, 'wb') as f:
            pickle.dump(htree_new, f)
        htree += htree_new

    if os.path.isfile(etree_path):
        print(f'Loading etree from {etree_path}')
        with open(etree_path, 'rb') as f:
            etree_cached = pickle.load(f)
        etree = etree_cached
    else:
        engine = start_engine(args.engine, args.ms)
        print('Making engine tree...')
        board = chess.Board()
        etree = {}
        search(board, engine, etree, htree, args.treshold)
        print() # search uses \r, so we want a free line to keep the last output
        print(f'Saving to {etree_path}...')
        with open(etree_path, 'wb') as f:
            pickle.dump(etree, f)

    print('Making pv tree')
    pv_tree = make_pv_tree(htree, etree, args.treesize)
    print_pv_tree(pv_tree)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('year', type=int, default=2013, help='Start year')
    parser.add_argument('month', type=int, default=1, help='Start month')
    parser.add_argument('--engine', help='Engine path')
    parser.add_argument('--games', default=10**6, type=int, help='Maximum number of games to use from each month')
    parser.add_argument('--treshold', default=100, type=int, help='Minimum visits on nodes to expand')
    parser.add_argument('--ms', default=50, type=int, help='Miliseconds to search each leaf node')
    parser.add_argument('--treesize', default=50, type=int, help='Number of nodes to include in pv tree')
    args = parser.parse_args()

    max_year = datetime.datetime.now().year
    htree = collections.Counter()
    for year in range(2013, max_year+1):
        for month in range(1, 13):
            if (year, month) < (args.year, args.month): continue
            process_date(year, month, htree, args)


if __name__ == '__main__':
    main()


