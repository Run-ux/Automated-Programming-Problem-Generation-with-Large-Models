# C. Bride of Pipe Stream

## Description
Thestorycontinues! Forseveralyearsnow,yourtownhasbeengiftedwithanabundanceofFlubber,the
adorable-but-slightly-flammable-and-toxic-and-acidic-and-sentient-and-mischievous man-made chemi-
cal. The search continues for more (or, well, any) uses for the substance. But in the meantime, the
Flubber factory continues to produce it at full capacity. Efforts to shut it down have failed, partly be-
causenobodyissurewhoisactuallyrunningthefactory.
You’vebeentaskedwithstoringtheperpetually-flowingFlubberinvariousFlubberreservoirsforfuture
use (or, at least, to get it out of everyone’s hair – literally). To accomplish this, you have access to a
complicatednetworkofFlubberducts,connectingupvariousFlubberstationsandreservoirs.
Every Flubber station has one or more Flubber ducts leading from it, and has various gates that may
be raised or lowered so that incoming Flubber will drain into the output Flubber ducts in any desired
proportion. For instance, you can send all the Flubber down one duct, or split it between two ducts
25–75,etc.
Incontrast,aFlubberductflowsdowntooneormorelowerstationsorreservoirs,buttheFlubberdrains
intotheminafixedproportionthatyoudonotcontrol. ItispossiblethatsomeoftheFlubberislostto
theenvironmentaswell,butthatisaproblemforyoursuccessor,notyou.
You would like to fill all the reservoirs as quickly as possible. That is, you want to maximize the
minimum amount of Flubber flowing into any of the reservoirs, among all possible configurations of
stationdrainage.
Figure C.1 illustrates the two sample inputs. Stations and reservoirs are shown as numbered nodes,
colored green for stations and blue for reservoirs. Ducts are depicted as white nodes. For example, in
thefirstsampleinput(left),Flubbercanbesentfromstation1inanyproportiontoitstwodownstream
ducts,buteachductwilldistributeitsinflowaccordingtothepercentagesprintedonitsoutgoingedges.
1
1
40%
2
80% 10% 30%
50% 40% 60% 50%
100%
3 4 5 2 3
FigureC.1: Illustrationsofthetwosampleinputs.

## Input
The first line of input contains three integers s, r, and d, where s (1 s 10000) is the number of
≤ ≤
stations,r (1 r 3)isthenumberofreservoirs,andd(s d 20000)isthenumberofducts. The
≤ ≤ ≤ ≤
stations are numbered from 1 to s and the reservoirs are numbered from s+1 to s+r, in decreasing
orderofaltitude. Thefactory’sFlubberinitiallyflowsintostation1.
49thICPCWorldChampionshipProblemC:BrideofPipeStream©ICPCFoundation 5
Each of the remaining d lines starts with two integers i and n, where i (1 i s) is the station that
≤ ≤
candrainintothisduct,andn(1 n 10)isthenumberofoutputsofthisduct. Theremainderofthe
≤ ≤
linecontainsnpairsofintegersoandp,whereo(i < o s+r)isastationorreservoirtowhichthis
≤
ductdrains,andp(1 p 100)isthepercentageoftheFlubberenteringtheductthatwilldraintoo.
≤ ≤
Theovaluesforagivenductaredistinct. Everystationhasatleastoneductthatitcandraininto. The
percentagesforagivenduct’soutputswillsumtoatmost100.

## Output
Outputasinglepercentagef,whichisthehighestpossiblepercentagesuchthat,forsomeconfiguration
of station drainage, all reservoirs receive at least f% of the factory’s produced Flubber. Your answer
shouldhaveanabsoluteerrorofatmost10−6.
Sample Input 1 Sample Output 1
2 3 3 24.0
1 2 3 80 4 10
1 2 2 40 4 30
2 1 5 100
Sample Input 2 Sample Output 2
1 2 3 42.8571428571
1 1 2 50
1 1 3 50
1 2 2 40 3 60
49thICPCWorldChampionshipProblemC:BrideofPipeStream©ICPCFoundation 6

## Constraints
(Not found)
