# J. Stacking Cups

## Description
Youhaveacollectionofncylindricalcups,wheretheith cupis2i 1cmtall. Thecupshaveincreasing
−
diameters,suchthatcupifitsinsidecupj ifandonlyifi < j. Thebaseofeachcupis1cmthick(which
makesthesmallestcupratheruselessasitisonly1cmtall,butyoukeepitforsentimentalreasons).
Afterwashingallthecups,youstacktheminatower. Eachcupisplacedupright(inotherwords,with
theopeningatthetop)andwiththecentersofallthecupsalignedvertically. Theheightofthetoweris
definedastheverticaldistancefromthelowestpointonanyofthecupstothehighest. Youwouldlike
toknowinwhatordertoplacethecupssuchthatthefinalheight(incm)isyourfavoritenumber. Note
thatallncupsmustbeused.
Forexample,supposen = 4andyourfavoritenumberis9. Ifyouplacethecupsofheights7,3,5,1,in
thatorder,thetowerwillhaveatotalheightof9,asshowninFigureJ.1.
9
8
7
6
5
4
3
2
1
0
FigureJ.1: IllustrationofSampleOutput1.

## Input
The input consists of a single line containing two integers n and h, where n (1 n 2 105) is the
≤ ≤ ·
numberofcupsandh(1 h 4 1010)isyourfavoritenumber.
≤ ≤ ·

## Output
Ifitispossibletobuildatowerwithheighth,outputtheheightsofallthecupsintheordertheyshould
beplacedtoachievethis. Otherwise,outputimpossible. Ifthereismorethanonevalidorderingof
cups,anyonewillbeaccepted.
49thICPCWorldChampionshipProblemJ:StackingCups©ICPCFoundation 19
Sample Input 1 Sample Output 1
4 9 7 3 5 1
Sample Input 2 Sample Output 2
4 100 impossible
49thICPCWorldChampionshipProblemJ:StackingCups©ICPCFoundation 20

## Constraints
(Not found)
