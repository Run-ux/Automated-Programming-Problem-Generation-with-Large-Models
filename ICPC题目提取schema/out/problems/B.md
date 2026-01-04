# B. Blackboard Game

## Description
Tohelpherelementaryschoolstudentsunderstandtheconceptofprimefactorization,Aishahasinvented
agameforthemtoplayontheblackboard. Therulesofthegameareasfollows.
The game is played by two players who alternate their moves. Initially, the integers from 1 to n are
writtenontheblackboard. Tostart,thefirstplayermaychooseanyevennumberandcircleit. Onevery
subsequent move, the current player must choose a number that is either the circled number multiplied
bysomeprime,orthecirclednumberdividedbysomeprime. Thatplayerthenerasesthecirclednumber
and circles the newly chosen number. When a player is unable to make a move, that player loses the
game.
TohelpAisha’sstudents,writeaprogramthat,giventheintegern,decideswhetheritisbettertomove
firstorsecond,andifitisbettertomovefirst,figuresoutawinningfirstmove.

## Input
The first line of input contains an integer t (1 t 40), which is the number of test cases. The
≤ ≤
descriptionsofttestcasesfollow.
Each test case consists of a single line containing an integer n (2 n 107), which is the largest
≤ ≤
numberwrittenontheblackboard.
Overalltestcases,thesumofnisatmost107.

## Output
For each test case, if the first player has a winning strategy for the given n, output the word first,
followed by an even integer – any valid first move that can be extended to a winning strategy. If the
secondplayerhasawinningstrategy,outputjustthewordsecond.
Sample Input 1 Sample Output 1
1 second
5
ExplanationofSample1: Forn = 5,thefirstplayerlosesthegameregardlessofthefirstmove.
• Ifthefirstplayerstartswith2,thesecondplayercircles4,andtherearenomorevalidmovesleft.
• If the first move is 4, the second player circles 2. The first player must then circle 1, and the
secondplayermaypickeitheroftheremainingtwonumbers(3or5)towin.
Sample Input 2 Sample Output 2
2 first 8
12 first 6
17
49thICPCWorldChampionshipProblemB:BlackboardGame©ICPCFoundation 3
This page is intentionally left blank.

## Constraints
(Not found)
