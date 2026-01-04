# F. Herding Cats

## Description
YouareopeningacatcafeinBakuandwouldliketotakeapromotionalphotographofallthecatssitting
in the front window. Unfortunately, getting cats to do what you want is a famously hard problem. But
you have a plan: you have bought a collection of m catnip plants, each of a different variety, knowing
thateachcatlikessomeofthesevarieties. Thereisarowofmpotsinthewindow,numbered1tomin
order,andyouwillplaceoneplantineachpot. Eachcatwillthenbepersuaded(bymeansofatoyona
string)towalkalongtherowofpotsfrom1tom. Assoonasacatreachesapotwithacatnipplantthat
itlikes,itwillstopthere,eveniftherealreadyareothercatsatthatplant.
FigureF.1: Onepossibleplantorderingforthefirstsampletestcase.
You know which pot you would like each cat to stop beside. Can you find a way in which to place the
plantsinthepotstoachievethis?

## Input
The first line of input contains an integer t (1 t 10000), which is the number of test cases. The
≤ ≤
descriptionsofttestcasesfollow.
Thefirstlineofeachtestcasecontainstwointegersnandm,wheren(1 n 2 105)isthenumber
≤ ≤ ·
of cats, and m (1 m 2 105) is the number of catnip plants (and also the number of pots). Catnip
≤ ≤ ·
plantsarenumberedfrom1tom.
The following n lines each describe one cat. The line starts with two integers p and k, where p (1
≤
p m)isthepotatwhichthecatshouldstop,andk(1 k m)isthenumberofcatnipplantsthecat
≤ ≤ ≤
likes. Theremainderofthelinecontainskdistinctintegers,whicharethenumbersoftheplantsthatthe
catlikes.
Overalltestcases,thesumofnisatmost2 105,thesumofmisatmost2 105,andthesumofallk
· ·
isatmost5 105.
·
49thICPCWorldChampionshipProblemF:HerdingCats©ICPCFoundation 11

## Output
Foreachtestcase,outputeitheryesifitispossibletoarrangethecatnipplantsasdescribedabove,or
noifnot.
Sample Input 1 Sample Output 1
2 yes
3 5 no
2 2 1 5
2 3 1 4 5
4 2 3 4
3 5
2 2 1 5
2 3 1 4 5
5 2 3 4
Explanation of Sample 1: In the first test case, a possible ordering of the plants is [2,1,5,3,4]. This
way,cat1willstopatpot2,asitisthefirstpotwithaplantvarietythatitlikes. Cat2willstopthereas
well. Cat3willcontinueallthewaytopot4,asshowninFigureF.1.
49thICPCWorldChampionshipProblemF:HerdingCats©ICPCFoundation 12

## Constraints
(Not found)
