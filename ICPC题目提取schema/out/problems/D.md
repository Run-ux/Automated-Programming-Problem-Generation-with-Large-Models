# D. Buggy Rover

## Description
The International Center for Planetary Cartography (ICPC) uses
rovers to explore the surfaces of other planets. As we all know,
other planets are flat surfaces which can be perfectly and evenly
discretizedintoarectangulargridstructure. Eachcellinthisgrid
iseitherflatandcanbeexploredbytherover,orrockyandcannot.
Today marks the launch of their brand-new Hornet rover. The
roverissettoexploretheplanetusingasimplealgorithm. Inter-
nally, the rover maintains a direction ordering, a permutation of
MarsroverbeingtestedneartheParanalObservatory.
thedirectionsnorth,east,south,andwest. Whentherovermakes CCBY-SA4.0byESO/G.
HudepohlonWikimediaCommons
a move, it goes through its direction ordering, chooses the first
direction that does not move it off the face of the planet or onto
animpassablerock,andmakesonestepinthatdirection.
Between two consecutive moves, the rover may be hit by a cosmic ray, replacing its direction ordering
with a different one. ICPC scientists have a log of the rover’s moves, but it is difficult to determine by
handifandwhentherover’sdirectionorderingchanged. Giventhemovesthattheroverhasmade,what
isthesmallestnumberoftimesthatitcouldhavebeenhitbycosmicrays?

## Input
Thefirstlineofinputcontainstwointegersrandc,wherer(1 r 200)isthenumberofrowsonthe
≤ ≤
planet,andc(1 c 200)isthenumberofcolumns. Therowsrunnorthtosouth,whilethecolumns
≤ ≤
runwesttoeast.
Thenextrlineseachcontainccharacters,representingthelayoutoftheplanet. Eachcharacteriseither
‘#’, a rocky space; ‘.’, a flat space; or ‘S’, a flat space that marks the starting position of the rover.
Thereisexactlyone‘S’inthegrid.
Thefollowinglinecontainsastrings,whereeachcharacterofsis‘N’,‘E’,‘S’,or‘W’,representingthe
sequence of the moves performed by the rover. The string s contains between 1 and 10000 characters,
inclusive. Allofthemovesleadtoflatspaces.

## Output
Outputtheminimumnumberoftimestherover’sdirectionorderingcouldhavechangedtobeconsistent
withthemovesitmade.
49thICPCWorldChampionshipProblemD:BuggyRover©ICPCFoundation 7
Sample Input 1 Sample Output 1
5 3 1
#..
...
...
...
.S.
NNEN
ExplanationofSample1: Therover’sdirectionorderingcouldbeasfollows. Inthefirstmove,iteither
prefers to go north, or it prefers to go south and then north. Note that in the latter case, it cannot move
southasitwouldfallfromthefaceoftheplanet. Inthesecondmove,itmustprefertogonorth. Inthe
third move, it must prefer to go east. In the fourth move, it can either prefer to go north, or east and
then north. It is therefore possible that it was hit by exactly one cosmic ray between the second and
third move, changing its direction ordering from N??? to EN?? where ‘?’ stands for any remaining
direction.
Sample Input 2 Sample Output 2
3 5 0
.###.
....#
.S...
NEESNS
Explanation of Sample 2: It is possible the rover began with the direction ordering NESW, which is
consistentwithallmovesitmakes.
Sample Input 3 Sample Output 3
3 3 4
...
...
S#.
NEESNNWWSENESS
49thICPCWorldChampionshipProblemD:BuggyRover©ICPCFoundation 8

## Constraints
(Not found)
