import chess, chess.pgn, chess.engine
import bz2, requests, gzip
import collections, heapq
import os.path, pickle
import math, random
import argparse, datetime


class Engine:
    def __init__(self, ucipath, search_time, threads):
        """
        Spawn a new uci engine from the given path.
        """
        self.engine = None
        self.search_time = search_time
        self.threads = threads
        self.ucipath = ucipath
        self.evals = 0

    def start(self):
        self.engine = chess.engine.SimpleEngine.popen_uci(self.ucipath)
        self.engine.configure({'Threads': self.threads})

    def evaluate(self, board):
        """
        Evaluate the board using the given engine.
        Returns the best move as well as the score from the perspective
        of the current player in the range [-1, 1].
        """
        self.evals += 1
        info = self.engine.analyse(board, chess.engine.Limit(time=self.search_time))
        wp = info['score'].relative.wdl().expectation()
        #wp = 2/(1 + 10**(-cp/400)) - 1
        move = info['pv'][0]
        return move, wp


class GameDatabase:
    archive_url = 'https://database.lichess.org/standard/lichess_db_standard_rated_{year:04d}-{month:02d}.pgn.bz2'

    def __init__(self):
        self.htree = collections.Counter()

    def download_games(self, year, month, max_games, filters):
        """
        Download and parsse lichess games from year, month.
        """
        url = self.archive_url.format(year=year, month=month)
        # For some reason the lichess server now defaults to gzipping the bzip
        headers = {'Accept-Encoding': 'identity'}
        with requests.get(url, headers=headers, stream=True) as r:
            r.raise_for_status()
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
                    if not all(f(game.headers) for f in filters):
                        continue
                    yield game

    def update_tree(self, year, month, max_games, filters):
        """
        Add games to a position -> visits counter.
        """
        games = self.download_games(year, month, max_games, filters)
        for i, game in enumerate(games):
            board = game.board()
            if i % 1000 == 0:
                print(i, 'games processed', end='\r')
            for j, move in enumerate(game.mainline_moves()):
                key = hash(board._transposition_key())
                self.htree[key] += 1
                self.htree[hash((key, move))] += 1
                # We only allow a game to contribute one new position.
                # This prevents our RAM from filling up with otherwise unseen
                # positions, while not affecting useful posistions much.
                if self.htree[key] == 1:
                    break
                board.push(move)
        print(i+1, 'games processed')
        # TODO: Consider trimming the tree by removing all nodes with less

    def get_board_count(self, board):
        key = hash(board._transposition_key())
        return self.htree[key]

    def get_move_count(self, board, move):
        key = hash(board._transposition_key())
        return self.htree[hash((key, move))]

    def dump(self, path):
        with open(path, 'wb') as f:
            pickle.dump(self.htree, f)

    def load_update(self, path):
        with open(path, 'rb') as f:
            self.htree += pickle.load(f)


class Expectimax:
    def __init__(self, engine, database, color, treshold):
        self.engine = engine
        self.treshold = treshold
        self.database = database
        self.color = chess.WHITE if color == 'white' else chess.BLACK
        self.etree = {}

    def search(self):
        """ Travels the tree top-down, evaluating the scores, storing them in etree """
        if self.color == chess.WHITE:
            self.__search(chess.Board())
        else:
            board = chess.Board()
            score = 0
            for p, move in self.most_common(board):
                board.push(move)
                score += p*self.__search(board)
                board.pop()
            self.etree[hash(board._transposition_key())] = (None, score)
        # search uses \r, so we want a free line to keep the last output
        print()

    def __search(self, board):
        """
        Perform expectimax. Could also use mcts.
        Search is always called from the perspective of ourselves
        """

        root_key = hash(board._transposition_key())

        if root_key in self.etree:
            value = self.etree[root_key]
            # We could be going in a circle.
            # No reason to break this in the probabilistically correct way
            if value == 'open':
                move, score = self.engine.evaluate(board)
                self.etree[root_key] = (move, score)
                return score
            best_move, best_score = value
            return best_score
        else:
            self.etree[root_key] = 'open'

        if self.database.get_board_count(board) < self.treshold:
            move, score = self.engine.evaluate(board)
            self.etree[root_key] = (move, score)
            return score

        print(self.engine.evals, '...', end='\r')

        best_move, best_score = None, -1
        for move in board.legal_moves:
            board.push(move)
            if self.database.get_board_count(board) < self.treshold:
                # After applying our move, evaluate gives the score from
                # the perspective of our opponent, so we negate it.
                # TODO: Should we cache this?
                _, mscore = self.engine.evaluate(board)
                score = -mscore
            else:
                score = 0
                denom = 0
                for opp_move in board.legal_moves:
                    board.push(opp_move)
                    val = self.__search(board)
                    board.pop()
                    # We use a Laplace smoothing, adding 1 to each move.
                    move_cnt = self.database.get_move_count(board, opp_move) + 1
                    score += val * move_cnt
                    denom += move_cnt
                score /= denom
            board.pop()
            # From our own perspective, we always pick the best move.
            # Expecti-max style.
            if score >= best_score:
                best_move = move
                best_score = score

        self.etree[root_key] = (best_move, best_score)
        return best_score

    def print_pv_tree(self, n):
        self.__inner_pv_tree(self.__make_pv_tree(n), chess.Board(), indent='',
                             has_siblings=False)

    def __inner_pv_tree(self, pv_tree, board, indent, has_siblings):
        for p, move, subtree in pv_tree:
            if move is None:
                print(indent, f'Score: {p:.2f}')
            else:
                if board.turn == self.color:
                    print(indent, f'{board.san(move)}. Score: {p:.2f}')
                else:
                    print(indent, f'{board.san(move)} ({p:.2f})')
                board.push(move)
            subindent = indent + (' | ' if has_siblings else ' '*3)
            self.__inner_pv_tree(subtree, board, subindent,
                                 has_siblings=len(subtree) > 1)
            if move is not None:
                board.pop()

    def __make_pv_tree(self, n):
        """
        n is the number nodes in the tree
        """
        q = [] # (-logp, p, random, move, board, tree-where-it-should-live)
        tree = []
        self.__push_children(q, tree, 0, chess.Board())

        while n != 0 and q:
            # Get and add node from heap
            mlogp, _, p, move, board, subtree = heapq.heappop(q)
            sub2tree = []
            subtree.append((p, move, sub2tree))
            self.__push_children(q, sub2tree, mlogp, board)
            n -= 1

        return tree

    def __push_children(self, q, tree, mlogp, board):
        # Get and add response node
        key = hash(board._transposition_key())
        if key not in self.etree: return
        move, score = self.etree[key]
        #if move is None and not ignore_none: return
        subtree = []
        tree.append((score, move, subtree))
        # If we are at the root, the move is a null-move (changing the color
        # from black to white) so we don't push it.
        if move is not None:
            board.push(move)
        # Add response-response nodes to heap
        for pp, move in self.most_common(board):
            board.push(move)
            heapq.heappush(q, (mlogp - math.log(pp), random.random(), pp, move, board.copy(), subtree))
            board.pop()

    def most_common(self, board):
        res = []
        total = 0
        for move in board.legal_moves:
            cnt = self.database.get_move_count(board, move)
            if cnt != 0:
                res.append((cnt, move))
                total += cnt
        res = [(cnt/total, move) for cnt, move in res]
        res.sort(reverse=True, key=lambda ab: ab[0])
        return res

    def load(self, path):
        with open(path, 'rb') as f:
            self.etree = pickle.load(f)

    def dump(self, path):
        with open(path, 'wb') as f:
            pickle.dump(self.etree, f)


class ChessOpeningsExpectimax:
    def main(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('year', type=int, default=2013, help='Start year')
        parser.add_argument('month', type=int, default=1, help='Start month')
        parser.add_argument('--engine', help='Engine path')
        parser.add_argument('--games', default=10**6, type=int, help='Maximum number of games to use from each month')
        parser.add_argument('--treshold', default=100, type=int, help='Minimum visits on nodes to expand')
        parser.add_argument('--ms', default=50, type=int, help='Miliseconds to search each leaf node')
        parser.add_argument('--threads', default=4, type=int, help='Threads to use for engine')
        parser.add_argument('--treesize', default=50, type=int, help='Number of nodes to include in pv tree')
        parser.add_argument('--color', default='white', type=str, help='Side from which to analyze')
        parser.add_argument('--min-rating', default=0, type=int, help='Lowest rating for players')
        parser.add_argument('--max-rating', default=10000, type=int, help='Highest rating for players')
        parser.add_argument('--min-tc', default=0, type=int, help='Shortest time control (in seconds) to include')
        parser.add_argument('--max-tc', default=10000, type=int, help='Longest time control (in seconds) to include')
        args = parser.parse_args()

        max_year = datetime.datetime.now().year
        database = GameDatabase()
        for year in range(2013, max_year+1):
            for month in range(1, 13):
                if (year, month) < (args.year, args.month): continue
                self.process_date(year, month, database, args)

    def process_date(self, year, month, database, args):
        htree_path = f'htree_{year}_{month}.pkl'
        etree_path = f'etree_{args.color}_{year}_{month}.pkl'
        engine = Engine(args.engine, args.ms/1000, args.threads)
        searcher = Expectimax(engine, database, args.color, args.treshold)

        def header_filter(headers):
            welo, belo = headers['WhiteElo'], headers['BlackElo']
            if not welo.isdigit() or not belo.isdigit():
                #print('Warning; non digit elos:', welo, belo)
                return False
            welo, belo = int(welo), int(belo)
            if not args.min_rating <= welo <= args.max_rating \
                    or not args.min_rating <= belo <= args.max_rating:
                return False
            # This is important the same way rating filters are.
            if not '+' in headers['TimeControl']:
                # print('Warning: Odd tc', headers['TimeControl'])
                return False
            else:
                time, incr = headers['TimeControl'].split('+')
                secs = int(time) + 40*int(incr)
                if not args.min_tc <= secs <= args.max_tc:
                    return False
            return True

        if os.path.isfile(htree_path):
            print(f'Loading htree from {htree_path}')
            database.load_update(htree_path)
        else:
            # If we redo htree we also have to redo etree
            if os.path.isfile(etree_path):
                print(f'Removing {etree_path}')
                os.remove(etree_path)
            print('Making human tree from download...')
            database.update_tree(year, month, args.games, [header_filter])
            print(f'Saving to {htree_path}...')
            database.dump(htree_path)

        if os.path.isfile(etree_path):
            print(f'Loading etree from {etree_path}')
            searcher.load(etree_path)
        else:
            engine.start()
            print(f'Making engine tree for {args.color}...')
            searcher.search()
            print(f'Saving to {etree_path}...')
            searcher.dump(etree_path)

        print('Making pv tree')
        searcher.print_pv_tree(args.treesize)


if __name__ == '__main__':
    ChessOpeningsExpectimax().main()



