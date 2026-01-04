# G. Lava Moat

## Description
These pesky armies of good are coming to disturb the quiet and peaceful lands of the goblins again.
Buildingahugewalldidn’tworkoutthatwell,andsothegoblinsaregoingtoturntothetriedandtrue
stapleofdefense: amoatfilledwithlava. Theywanttodigthismoatasaboundarybetweenthegoblin
landsinthenorthandthedo-gooderlandsinthesouth,crossingthewholeborderlandswest-to-east.
Thispresentsthemwithachallenge. Theborderlandsarehilly,ifnotoutrightmountainous,whilealava
moathastobeallononelevel–otherwisethelavafromthehigherpartswillflowdownandoutofthe
moatinthelowerparts. So,thegoblinshavetochooseapaththatisallononeelevation,andconnects
the western border of the borderlands to its eastern border. For obvious economic reasons, they want
thispathtobeasshortaspossible.
This is where you come in. You are given an elevation map of the borderlands, and your task is to
determinehowshortthemoatcanbe.
Themapisintheformofafullytriangulatedrectanglewithdimensionsw ℓ,withalltriangleshaving
×
positivearea. Novertexofatriangleliesontheinteriorofanedgeofanothertriangle. Thesouthwestern
cornerofthemaphascoordinates(0,0),withthex-axisgoingeastandthey-axisgoingnorth. Further-
more, the western border (the line segment connecting (0,0) and (0,ℓ), including the endpoints) is a
singleedge. Similarly,theeasternborder(betweenpoints(w,0)and(w,ℓ))isalsoasingleedge.
Of course, this map is just a 2D projection of the actual 3D terrain: Every point (x,y) also has an
elevation z. The elevation at the vertices of the triangulation is directly specified by the map, and
all of these given elevations are distinct. The elevation at all other points can be computed by linear
interpolationonassociatedtriangles. Inotherwords,theterrainisshapedlikeacollectionoftriangular
facesjoinedtogetherbysharedsides. Thesefacescorrespondtothetrianglesonthemap.
FigureG.1: Illustrationofthesampletestcases. Shadingdenoteselevation,andthethick
redlinesdenoteoptimalmoats.

## Input
The first line of input contains an integer t (1 t 10000), which is the number of test cases. The
≤ ≤
descriptionsofttestcasesfollow.
The first line of each test case contains four integers w, ℓ, n, and m, where w (1 w 106) is
≤ ≤
the extent of the borderlands from west to east, ℓ (1 ℓ 106) is the extent from south to north,
≤ ≤
n(4 n 50000)isthenumberofvertices,andm(n 2 m 2n 6)isthenumberoftriangles
≤ ≤ − ≤ ≤ −
intheprovidedtriangulation.
49thICPCWorldChampionshipProblemG:LavaMoat©ICPCFoundation 13
This is followed by n lines, the ith of which contains three integers x , y , and z (0 x w;
i i i i
≤ ≤
0 y ℓ; 0 z 106), denoting the coordinates and the elevation of vertex i. The only vertices
i i
≤ ≤ ≤ ≤
withx = 0orx = w arethefourcorners. Allpairs(x ,y )aredistinct. Allz saredistinct.
i i i i i
Each of the following m lines contains three distinct integers a, b, and c (1 a,b,c n), denoting a
≤ ≤
map triangle formed by vertices a, b, and c in counter-clockwise order. These triangles are a complete
triangulationoftherectangle[0,w] [0,ℓ]. Eachofthenverticesisreferencedbyatleastonetriangle.
×
Overalltestcases,thesumofnisatmost50000.

## Output
Foreachtestcase,ifitispossibletoconstructalavamoatatasingleelevationthatconnectsthewestern
border to the eastern border, output the minimum length of such a moat, with an absolute or relative
errorofatmost10−6. Otherwise,outputimpossible.
Sample Input 1 Sample Output 1
3 impossible
6 6 4 2 6.708203932
0 0 1 15.849260054
6 0 4
6 6 3
0 6 2
1 2 3
1 3 4
6 6 4 2
0 0 1
6 0 2
6 6 4
0 6 3
1 2 3
1 3 4
10 6 7 7
6 1 8
10 0 10
10 6 4
2 6 6
0 6 0
4 3 11
0 0 7
2 1 7
2 3 1
3 6 1
3 4 6
6 4 5
5 7 6
7 1 6
49thICPCWorldChampionshipProblemG:LavaMoat©ICPCFoundation 14

## Constraints
(Not found)
