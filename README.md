# Chess Openings with Expectimax
In real chess, our opponent doesn't always play the best move.
Given a large database of games, we may expect they play according to the emperical probability distribution of what other players did in the same situation.
Consequently the right algorithm for chess search is not minimax, but expectimax.
That is, we want to optimize the expected outcome out of the opening.

This project uses the lichess database to perform such an analysis of the chess opening game.
An example run is the principal variation tree below, featuring the 50 most likely positions following said strategy, using the lichess game from January 2016.
The most likely variation - when we play as white - turns out to be the Italian Game with Ng5.

```
$python3 analyze_tree.py 2016 1 --engine ../Stockfish/src/stockfish
 e4. Score: 0.43
    e5: 0.38
    |  Nf3. Score: 0.48
    |     Nc6: 0.59
    |     |  Bc4. Score: 0.47
    |     |     Nf6: 0.33
    |     |     |  Ng5. Score: 0.51
    |     |     |     d5: 0.79
    |     |     |        exd5. Score: 0.46
    |     |     |           Nxd5: 0.44
    |     |     |           |  Nxf7. Score: 0.70
    |     |     |           |     Kxf7: 0.91
    |     |     |           |        Qf3+. Score: 0.66
    |     |     |           Na5: 0.41
    |     |     |           |  Bb5+. Score: 0.29
    |     |     |           |     c6: 0.85
    |     |     |           |        dxc6. Score: 0.34
    |     |     |           |           bxc6: 0.96
    |     |     |           |              Bd3. Score: 0.31
    |     |     Bc5: 0.27
    |     |     |  c3. Score: 0.46
    |     |     |     Nf6: 0.55
    |     |     |        O-O. Score: 0.45
    |     |     h6: 0.17
    |     |     |  d4. Score: 0.48
    |     |     |     exd4: 0.67
    |     |     |        Nxd4. Score: 0.43
    |     d6: 0.21
    |     |  d4. Score: 0.44
    |     |     exd4: 0.49
    |     |        Nxd4. Score: 0.33
    |     Nf6: 0.08
    |     |  Bc4. Score: 0.47
    c5: 0.20
    |  c3. Score: 0.36
    |     Nc6: 0.28
    |     |  d4. Score: 0.42
    |     |     cxd4: 0.80
    |     |        cxd4. Score: 0.44
    |     |           d5: 0.37
    |     |              exd5. Score: 0.43
    |     e6: 0.18
    |     |  d4. Score: 0.32
    |     |     cxd4: 0.54
    |     |        cxd4. Score: 0.35
    |     d6: 0.18
    |     |  d4. Score: 0.38
    |     |     cxd4: 0.80
    |     |        cxd4. Score: 0.38
    |     d5: 0.14
    |     |  exd5. Score: 0.32
    |     |     Qxd5: 0.92
    |     |        d4. Score: 0.31
    |     Nf6: 0.09
    |     |  e5. Score: 0.31
    |     |     Nd5: 0.99
    |     |        d4. Score: 0.28
    e6: 0.12
    |  d4. Score: 0.37
    |     d5: 0.64                                                              
    |        Nc3. Score: 0.35
    |           Nf6: 0.32
    |           |  Bg5. Score: 0.33
    |           Bb4: 0.26
    |           |  Bd3. Score: 0.29
    |           dxe4: 0.23
    |           |  Nxe4. Score: 0.37
    d5: 0.09
    |  exd5. Score: 0.46
    |     Qxd5: 0.69
    |     |  Nf3. Score: 0.47
    |     |     Qd8: 0.27
    |     |        Bc4. Score: 0.46
    |     Nf6: 0.20
    |     |  d4. Score: 0.38
    c6: 0.06
    |  d4. Score: 0.39
    |     d5: 0.87
    |        e5. Score: 0.39
    |           Bf5: 0.74
    |              Nc3. Score: 0.42
    |                 e6: 0.91
    |                    g4. Score: 0.42
    |                       Bg6: 0.99
    |                          Nge2. Score: 0.30
    d6: 0.04
    |  Nf3. Score: 0.38
    g6: 0.03
    |  d4. Score: 0.40
    |     Bg7: 0.88
    |        Nf3. Score: 0.40
    Nf6: 0.02
    |  e5. Score: 0.42
    |     Nd5: 0.87
    |        d4. Score: 0.39
    b6: 0.02
    |  d4. Score: 0.42
    |     Bb7: 0.86
    |        Nc3. Score: 0.41
    Nc6: 0.02
    |  Nf3. Score: 0.47
```

Notice that no filtering on black's rating was done, so both good and bad players influenced the learned probability distribution. 
There was also no filtering on the length of the games, so most games included can be assumed to be blitz games.
Finally note that some of the lines above may not be sound against a perfect opponent. It is only guaranteed that we get the highest win chance in average.
Here win-chance is calculated using stockfish and the pawn-advantage to win-percentage formula from https://chessprogramming.wikispaces.com/Pawn%20Advantage%2C%20Win%20Percentage%2C%20and%20Elo
