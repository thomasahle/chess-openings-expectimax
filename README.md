# Chess Openings with Expectimax
In real chess, our opponent doesn't always play the best move.
Given a large database of games, we may expect they play according to the emperical probability distribution of what other players did in the same situation.
Consequently the right algorithm for chess search is not minimax, but [expectimax](https://www.youtube.com/watch?v=jaFRyzp7yWw).
That is, we want to optimize the expected outcome out of the opening.

This project uses the lichess database to perform such an analysis of the chess opening game.
An example run is the principal variation tree below, featuring the 50 most likely positions following said strategy, using the lichess game from January 2016.
The most likely variation - when we play as white - turns out to be the Italian Game with Ng5.

```
$python3 analyze_tree.py 2017 1 --engine ../Stockfish/src/stockfish --ms 150
 e4. Score: 0.44
    e5 (0.43)
    |  Nf3. Score: 0.50
    |     Nc6 (0.61)
    |     |  Bc4. Score: 0.49
    |     |     Nf6 (0.34)
    |     |     |  Ng5. Score: 0.57
    |     |     |     d5 (0.80)
    |     |     |        exd5. Score: 0.51
    |     |     |           Nxd5 (0.45)
    |     |     |           |  Nxf7. Score: 0.70
    |     |     |           |     Kxf7 (0.92)
    |     |     |           |        Qf3+. Score: 0.67
    |     |     |           Na5 (0.41)
    |     |     |           |  Bb5+. Score: 0.35
    |     |     |           |     c6 (0.81)
    |     |     |           |        dxc6. Score: 0.35
    |     |     |           |           bxc6 (0.96)
    |     |     |           |              Be2. Score: 0.34
    |     |     Bc5 (0.27)
    |     |     |  c3. Score: 0.42
    |     |     |     Nf6 (0.59)
    |     |     |        d4. Score: 0.41
    |     |     |           exd4 (0.93)
    |     |     |              e5. Score: 0.39
    |     |     h6 (0.17)
    |     |     |  O-O. Score: 0.51
    |     |     |     Nf6 (0.59)
    |     |     |        d4. Score: 0.50
    |     |     |           exd4 (0.66)
    |     |     |              e5. Score: 0.48
    |     |     d6 (0.07)
    |     |     |  Nc3. Score: 0.40
    |     d6 (0.19)
    |     |  d4. Score: 0.45
    |     |     exd4 (0.49)
    |     |        Nxd4. Score: 0.33
    |     Nf6 (0.09)
    |     |  Bc4. Score: 0.51
    c5 (0.18)
    |  Nc3. Score: 0.36
    |     Nc6 (0.41)
    |     |  Nf3. Score: 0.36
    |     |     e6 (0.30)
    |     |     |  d4. Score: 0.39
    |     |     |     cxd4 (0.78)
    |     |     |        Nxd4. Score: 0.37
    |     |     d6 (0.25)
    |     |     |  d4. Score: 0.37
    |     d6 (0.25)
    |     |  Nf3. Score: 0.33
    |     |     Nf6 (0.39)
    |     |        d4. Score: 0.32
    |     e6 (0.21)
    |     |  Nf3. Score: 0.37
    e6 (0.11)
    |  d4. Score: 0.38
    |     d5 (0.63)
    |        Nc3. Score: 0.36
    |           Nf6 (0.30)
    |           |  Bg5. Score: 0.31
    |           Bb4 (0.25)
    |           |  a3. Score: 0.34
    |           dxe4 (0.24)
    |           |  Nxe4. Score: 0.38
    d5 (0.09)
    |  exd5. Score: 0.47
    |     Qxd5 (0.71)
    |     |  Nf3. Score: 0.47
    |     |     Bg4 (0.27)
    |     |        Nc3. Score: 0.52
    |     Nf6 (0.20)
    |     |  d4. Score: 0.43
    c6 (0.05)
    |  d4. Score: 0.37
    |     d5 (0.86)
    |        e5. Score: 0.36
    |           Bf5 (0.72)
    |              Nc3. Score: 0.38
    |                 e6 (0.91)
    |                    g4. Score: 0.38
    |                       Bg6 (0.97)
    |                          Nge2. Score: 0.28
    d6 (0.04)
    |  d4. Score: 0.39
    g6 (0.03)
    |  d4. Score: 0.39
    |     Bg7 (0.88)
    |        Nf3. Score: 0.39
    Nf6 (0.02)
    |  e5. Score: 0.40
    |     Nd5 (0.88)
    |        c4. Score: 0.37
    |           Nb6 (0.93)
    |              c5. Score: 0.36
    b6 (0.02)
    |  Nc3. Score: 0.40
    |     Bb7 (0.84)
    |        d4. Score: 0.39
    Nc6 (0.02)
    |  Nf3. Score: 0.47
```
(This was let to run over 2 months, 2,000,000 games in total.)

Notice that no filtering on black's rating was done, so both good and bad players influenced the learned probability distribution. 
There was also no filtering on the length of the games, so most games included can be assumed to be blitz games.
Finally note that some of the lines above may not be sound against a perfect opponent. It is only guaranteed that we get the highest win chance in average.
Here win-chance is calculated using stockfish and the pawn-advantage to win-percentage formula from https://chessprogramming.wikispaces.com/Pawn%20Advantage%2C%20Win%20Percentage%2C%20and%20Elo

Below is the equivalent tree for black (run over two months, 2,000,000 games).
```
$python3 analyze_tree.py 2017 1 --engine stockfish --ms 150 --color black
 Score: 0.29
    e4 (0.60)
    |  e5. Score: 0.33
    |     Nf3 (0.61)
    |     |  Nc6. Score: 0.29
    |     |     Bc4 (0.37)
    |     |     |  Nf6. Score: 0.35
    |     |     |     Ng5 (0.36)
    |     |     |     |  d5. Score: 0.40
    |     |     |     |     exd5 (0.96)
    |     |     |     |        Nd4. Score: 0.39
    |     |     |     |           c3 (0.46)
    |     |     |     |           |  b5. Score: 0.12
    |     |     |     |           d6 (0.36)
    |     |     |     |           |  Qxd6. Score: 0.79
    |     |     |     d3 (0.27)
    |     |     |     |  Bc5. Score: 0.22
    |     |     |     Nc3 (0.16)
    |     |     |     |  Nxe4. Score: 0.41
    |     |     Bb5 (0.30)
    |     |     |  Nf6. Score: 0.19
    |     |     |     O-O (0.35)
    |     |     |     |  Nxe4. Score: 0.16
    |     |     |     |     Re1 (0.49)
    |     |     |     |        Nd6. Score: 0.12
    |     |     |     Bxc6 (0.25)
    |     |     |     |  dxc6. Score: 0.28
    |     |     |     d3 (0.20)
    |     |     |     |  Nd4. Score: 0.17
    |     |     |     Nc3 (0.15)
    |     |     |     |  Nd4. Score: 0.19
    |     |     d4 (0.16)
    |     |     |  exd4. Score: 0.30
    |     |     |     Nxd4 (0.74)
    |     |     |        Bc5. Score: 0.27
    |     |     |           Nxc6 (0.43)
    |     |     |           |  dxc6. Score: 0.22
    |     |     |           Be3 (0.37)
    |     |     |           |  Nxd4. Score: 0.37
    |     |     |           |     Bxd4 (0.98)
    |     |     |           |        Bxd4. Score: 0.28
    |     |     |           |           Qxd4 (0.99)
    |     |     |           |              Qf6. Score: 0.16
    |     |     Nc3 (0.10)
    |     |     |  Nf6. Score: 0.30
    |     Bc4 (0.10)
    |     |  Nf6. Score: 0.40
    |     |     d3 (0.36)
    |     |        c6. Score: 0.31
    |     f4 (0.07)
    |     |  d6. Score: 0.39
    |     |     Nf3 (0.82)
    |     |        exf4. Score: 0.37
    |     |           Bc4 (0.59)
    |     |              h6. Score: 0.39
    |     d4 (0.07)
    |     |  exd4. Score: 0.39
    |     |     Qxd4 (0.45)
    |     |        Nc6. Score: 0.36
    |     Nc3 (0.04)
    |     |  Nf6. Score: 0.30
    |     Qh5 (0.04)
    |     |  Nc6. Score: 0.54
    |     d3 (0.03)
    |     |  d5. Score: 0.28
    d4 (0.24)
    |  d5. Score: 0.22
    |     c4 (0.44)
    |     |  dxc4. Score: 0.20
    |     |     Nc3 (0.37)
    |     |     |  e5. Score: 0.25
    |     |     |     d5 (0.49)
    |     |     |        Nf6. Score: 0.25
    |     |     |           e4 (0.91)
    |     |     |              b5. Score: 0.15
    |     |     e3 (0.30)
    |     |     |  e5. Score: 0.18
    |     |     |     Bxc4 (0.75)
    |     |     |        Nc6. Score: 0.18
    |     |     e4 (0.18)
    |     |     |  b5. Score: 0.18
    |     Nf3 (0.17)
    |     |  c5. Score: 0.20
    |     e3 (0.13)
    |     |  Nf6. Score: 0.22
    |     Bf4 (0.08)
    |     |  Nf6. Score: 0.25
    |     Nc3 (0.07)
    |     |  Nf6. Score: 0.23
    Nf3 (0.04)
    |  d5. Score: 0.23
    c4 (0.03)
    |  e5. Score: 0.22
    |     Nc3 (0.57)
    |        Nf6. Score: 0.21
    e3 (0.02)
    |  e5. Score: 0.30
    g3 (0.02)
    |  d5. Score: 0.34
    |     Bg2 (0.86)
    |        Bh3. Score: 0.35
```
