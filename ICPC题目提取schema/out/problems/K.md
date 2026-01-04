# K. Treasure Map

## Description
AfteryearsofsearchingyouhavecomeacrossCaptainBlackbeard’soldmapshowingwherehislong-
losttreasureishidden,deepontheoceanfloor. Themapwasonceahypsometricmap–thatis,itshowed
the ocean depth for the region around the treasure – but many of the elevation marks have faded away
overtimeandarenolongerlegible.
Specifically, the map covers a rectangular part of the ocean, subdivided into an (n 1) (m 1)
− × −
rectangular grid of unit squares. The map originally showed the ocean depth d(p) for each point p =
(x,y) with integer coordinates 1 x n and 1 y m. There are no islets in the region. In other
≤ ≤ ≤ ≤
words,itisknownthatd(p) 0forallpoints.
≥
PreparingthemapmusthavebeenquiteastruggleforBlackbeard,sincethereisnouniquenaturalway
to interpolate the depths of points with non-integer coordinates. Consider a unit square on the grid,
withcornersatthegridpointsA,B,C,andD inclockwiseorder,andsomedepthd(p)storedforeach
p A,B,C,D . OnenaturalwayistointerpolatethedepthinthetriangleABC linearly,andlikewise
∈ { }
inCDA. AnotherequallynaturalwayistointerpolatelinearlywithinBCD,andlikewisewithinDAB.
Usually,theresultsofthosetwointerpolationsaredifferent. Forexample,ifd(A) = d(B) = d(C) = 0
andd(D) = 1,thefirstmethodresultsindepthsacrossallofABC beingequaltozero(FigureK.1left),
whilethesecondmethodresultsinthedepthsbeingpositiveinthewholeinteriorofthesquare(right).
A B A B
D C D C
FigureK.1: Twowaysofinterpolatingdepthswithinaunitsquare.
However, Blackbeard was as stubborn as he was cruel and would not let such pesky ambiguities stop
him. Tofindtheperfecthidingspotforhistreasure,hescouredthesevenseasforaregionoftheocean
wherethetwomethodsdescribedaboveyieldthesameresultsforeachunitsquare(ormaybeheforced
someofhispiratestodoabitofterraformingworktoachievethis–scholarsdisagree).
Backinthepresent,youarepreparinganexpeditiontoretrievethetreasure,andwouldliketofigureout
atwhatdepththetreasurecouldbeburied. Specifically,giventheremainingdepthdataofthemap,you
shouldcalculatethesmallestpossibledepthatthetreasurelocation.

## Input
The first line of input contains five integers n, m, k, t , and t , where n and m (2 n,m 3 105)
x y
≤ ≤ ·
denote the maximum coordinates of the grid, k (1 k 3 105) is the number of known depths, and
≤ ≤ ·
(t ,t )isthelocationofthetreasure(1 t n;1 t m). Eachofthenextklinescontainsthree
x y x y
≤ ≤ ≤ ≤
integers x, y, and d (1 x n; 1 y m; 0 d 109), indicating that the depth at coordinate
≤ ≤ ≤ ≤ ≤ ≤
(x,y)ofthegridequalsd. Eachpair(x,y)appearsintheinputatmostonce.
49thICPCWorldChampionshipProblemK:TreasureMap©ICPCFoundation 21

## Output
Iftheprovideddatapointscanbeextendedtoavalidmap(thatis,amapwhere,foreachunitsquare,the
twomethodsofinterpolationyieldthesameresults,andallpointshavenon-negativedepth),outputone
integer: thesmallestpossibledepthof(t ,t )–itcanbeshownthatthisisalwaysaninteger. Otherwise,
x y
outputimpossible.
Sample Input 1 Sample Output 1
3 3 5 1 1 3
1 3 1
3 3 2
2 3 3
2 2 4
2 1 5
Sample Input 2 Sample Output 2
3 5 4 3 4 1
2 4 1
2 2 2
1 1 4
3 1 5
Sample Input 3 Sample Output 3
3 3 3 3 3 0
2 3 1
2 1 2
1 2 4
Sample Input 4 Sample Output 4
3 3 4 3 2 impossible
2 1 2
2 3 3
1 3 4
1 1 5
Sample Input 5 Sample Output 5
3 3 3 2 2 impossible
3 2 0
2 2 1
2 3 0
ExplanationofSample5: Eventhoughthedepthof(2,2)isgivenintheinput,theprovideddatapoints
cannotbeextendedtoavalidmap,sothecorrectanswerisimpossible.
49thICPCWorldChampionshipProblemK:TreasureMap©ICPCFoundation 22

## Constraints
(Not found)
