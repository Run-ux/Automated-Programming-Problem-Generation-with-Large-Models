# L. Walking on Sunshine

## Description
I’mwalkingonsunshine,anditdon’tfeelgood–myeyeshurt!
Bakuhasplentyofsunshine. Ifyouwalkawayfromthesun,oratleastperpendiculartoitsrays,itdoes
not shine in your eyes. For this problem assume that the sun shines from the south. Walking west or
eastorinanydirectionbetweenwestandeastwithanorthwardcomponentavoidslookingintothesun.
Youreyeswillhurtifyouwalkinanydirectionwithasouthwardcomponent.
Baku also has many rectangular areas of shade, and staying in these protects your eyes regardless of
whichdirectionyouwalkin. Forexample,FigureL.1showstwoshadedareas.
Find the minimum distance you need to walk with the sun shining in your eyes to get from the contest
locationtotheawardsceremonylocation.
y
9
8 NW NE
7
6 WS ES
5
4
3
2
1
x
1 2 3 4 5 6 7 8 9 10 11
E
N
W
con•test
S
awardsc•eremony
FigureL.1: SampleInput1andapaththatminimizesthesunshininginyoureyes.

## Input
Thefirstlineofinputcontainsfiveintegersn,x ,y ,x ,andy ,wheren(0 n 105)isthenumberof
c c a a
≤ ≤
shadedareas,(x ,y )isthelocationofthecontest,and(x ,y )isthelocationoftheawardsceremony
c c a a
( 106 x ,y ,x ,y 106). The sun shines in the direction (0,1) from south towards north. You
c c a a
− ≤ ≤
lookintothesunifyouwalkindirection(x,y)foranyy < 0andanyx.
The next n lines describe the shaded areas, which are axis-aligned rectangles. Each of these lines
contains four integers x , y , x , and y ( 106 x < x 106; 106 y < y 106).
1 1 2 2 1 2 1 2
− ≤ ≤ − ≤ ≤
The southwest corner of the rectangle is (x ,y ) and its northeast corner is (x ,y ). The rectangles
1 1 2 2
describingtheshadedareasdonottouchorintersect.

## Output
Output the minimum distance you have to walk with the sun shining in your eyes. Your answer must
haveanabsoluteorrelativeerrorofatmost10−7.
49thICPCWorldChampionshipProblemL:WalkingonSunshine©ICPCFoundation 23
Sample Input 1 Sample Output 1
2 1 7 5 1 3.0
3 6 5 9
2 3 6 5
Explanation of Sample 1: Figure L.1 shows an optimal path from the contest location to the awards
ceremony location with 5 segments. On the first segment you walk away from the sun. On the second
andfourthsegmentsyouwalktowardsthesunbutinashadedarea. Onthethirdandfifthsegmentsyou
walktowardsthesunoutsidetheshadedareas. Thetotallengthofthesetwosegmentsis3.
Sample Input 2 Sample Output 2
2 0 10 10 0 7.0
2 7 3 8
4 3 8 5
Sample Input 3 Sample Output 3
2 11 -1 -1 11 0.0
2 7 3 8
4 3 8 5
Sample Input 4 Sample Output 4
3 1 5 9 5 0.0
-5 6 2 9
4 7 12 8
1 1 7 3
Sample Input 5 Sample Output 5
3 1 7 9 3 0.0
2 6 3 8
4 4 5 6
6 2 7 4
Sample Input 6 Sample Output 6
1 0 0 0 0 0.0
-5 -5 5 5
49thICPCWorldChampionshipProblemL:WalkingonSunshine©ICPCFoundation 24

## Constraints
(Not found)
