import chess, chess.pgn, chess.engine
import bz2, requests, gzip
import collections, heapq
import os.path, pickle
import math, random
import argparse, datetime, urllib


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
        of the current player in the range [0, 1].
        """
        self.evals += 1
        info = self.engine.analyse(board, chess.engine.Limit(time=self.search_time))
        wp = info['score'].relative.wdl().expectation()
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
                        print('Warning: EOFError')
                        break
                    except ConnectionResetError:
                        print('Warning: ConnectionResetError')
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
        i = -1 # In case there are no games
        for i, game in enumerate(games):
            board = game.board()
            print(i, 'games processed', end='\r')
            for j, move in enumerate(game.mainline_moves()):
                key = board._transposition_key()
                self.htree[key] += 1
                self.htree[(key, move)] += 1
                # We only allow a game to contribute one new position.
                # This prevents our RAM from filling up with otherwise unseen
                # positions, while not affecting useful posistions much.
                if self.htree[key] == 1:
                    break
                board.push(move)
        print(i+1, 'games processed')
        # TODO: Consider trimming the tree by removing all nodes with less

    def get_board_count(self, board):
        key = board._transposition_key()
        return self.htree[key]

    def get_move_count(self, board, move):
        key = board._transposition_key()
        return self.htree[(key, move)]

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
            self.etree[board._transposition_key()] = (None, score)
        # search uses \r, so we want a free line to keep the last output
        print()

    def __search(self, board):
        """
        Perform expectimax. Could also use mcts.
        Search is always called from the perspective of ourselves
        """

        root_key = board._transposition_key()

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

    def make_pgn(self, n):
        """ Makes a pgn, including the `n` most common nodes of the tree. """
        game = chess.pgn.Game()
        game.headers['Event'] = 'Expectimax analysis'
        self.__inner_make_pgn(self.__make_pv_tree(n), game)
        return game

    def __inner_make_pgn(self, pv_tree, node):
        for score_or_p, move, subtree in pv_tree:
            if move is None:
                # This only happens at the root, and only when we're black
                node.comment = f'Score: {2*score_or_p-1:.2f}'
                new_node = node
            else:
                board = node.board()
                new_node = node.add_variation(move)
                if board.turn == self.color:
                    new_node.comment = f'Score: {2*score_or_p-1:.2f}'
                else:
                    new_node.comment = f'Probability: {score_or_p:.2f}'
            self.__inner_make_pgn(subtree, new_node)

    def print_pv_tree(self, n):
        self.__inner_pv_tree(self.__make_pv_tree(n), chess.Board(), indent='',
                             has_siblings=False)

    def __inner_pv_tree(self, pv_tree, board, indent, has_siblings):
        for p, move, subtree in pv_tree:
            if move is None:
                # This only happens at the root, and only when we're black
                print(indent, f'Score: {p:.2f}')
            else:
                if board.turn == self.color:
                    print(indent, f'{board.san(move)}. Score: {2*p-1:.2f}')
                else:
                    print(indent, f'{board.san(move)} (p={p:.2f})')
                board.push(move)
            subindent = indent + (' | ' if has_siblings else ' '*3)
            self.__inner_pv_tree(subtree, board, subindent,
                                 has_siblings=len(subtree) > 1)
            if move is not None:
                board.pop()

    def __make_pv_tree(self, n):
        """
        Only incluedes the `n` most likely nodes in the tree.
        """
        q = [] # (-logp, p, random, move, board, tree-where-it-should-live)
        tree = []
        self.__push_children(q, tree, 0, chess.Board())

        while n != 0 and q:
            # Get and add node from heap
            mlogp, _, p, move, board, subtree = heapq.heappop(q)
            sub2tree = []
            # It's kinda odd: Here I add (p, move, subtree), but
            # in __push_children I add (score, move, ...). Probably this can
            # be done more elegantly.
            subtree.append((p, move, sub2tree))
            self.__push_children(q, sub2tree, mlogp, board)
            n -= 1

        return tree

    def __push_children(self, q, tree, mlogp, board):
        """ Let board be a node with our turn to play.
            Adds (score, move, subtree) to the tree, and then pushes all follow up
            moves to the heap with a reference to the subtree, so they can be expanded
            later on. """
        # Get and add response node
        key = board._transposition_key()
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
        """ Returns a list of (proability of play, move) pairs for the given position,
            based on the used GameDatabase. """
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
                print(f'\n{month} - {year}')
                self.process_date(year, month, database, args)

    def process_date(self, year, month, database, args):
        arg_dict = args.__dict__.copy()
        arg_dict['year'] = year
        arg_dict['month'] = month
        for arg in ['engine', 'threads', 'treesize']:
            del arg_dict[arg]
        arg_str = urllib.parse.urlencode(arg_dict)

        # TODO: There is no reason to include color=... in the htree path, since it
        # is the same from both sides
        htree_path = f'htree_{arg_str}.pkl' 
        etree_path = f'etree_{arg_str}.pkl'
        analysis_path = f'analysis_{arg_str}.pgn'
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
            size_prior = len(database.htree)
            database.load_update(htree_path)
            print(f'Loaded {len(database.htree) - size_prior} nodes')
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
            size_prior = len(searcher.etree)
            searcher.load(etree_path)
            print(f'Loaded {len(searcher.etree) - size_prior} nodes')
        else:
            engine.start()
            print(f'Making engine tree for {args.color}...')
            searcher.search()
            print(f'Saving to {etree_path}...')
            searcher.dump(etree_path)

        print('Making pv tree')
        searcher.print_pv_tree(args.treesize)

        print('Saving pgn analysis')
        pgn_game = searcher.make_pgn(50*args.treesize)
        print(pgn_game, file=open(analysis_path,'w'), end='\n\n')


if __name__ == '__main__':
    ChessOpeningsExpectimax().main()



