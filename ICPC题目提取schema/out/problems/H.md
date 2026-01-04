# H. Score Values

## Description
Ever since you arrived at your university, you have been a
tireless advocate for introducing the brand-new martial-arts-
plus-card-based sport of Contact Bridge to the school (and
the world). Finally, after a great deal of (really persistent
andannoying)advocacyonyourpart,youhaveobtainedper-
mission and funding from your dean to build a grand new
arena for the sport! Well, technically it is not so much an
“arena”asa“broomcloset,”andmaybenot“grand”somuch
as“cramped,”andthe“new”isalsodebatable. Butthesport
ofthefuturehastostartsomewhere! GeneratedbyChatGPT
Unfortunately,youjustrealizedthatyouaregoingtoneedascoredisplayinordertorunthegames. In
ContactBridge,thescoreforateamstartsat0and,aftervariousrepeatableactions,maybeincremented
by certain fixed amounts. There is also a maximum value – if the team’s score would be incremented
abovethemaximum,itwillinsteadbecappedthere. Youwanttheteam’sscoretobevisibleatalltimes,
so you will need to prepare some signs, each with a single digit printed on it, that can be arranged to
showthescore.
Unfortunately the dean’s “funding” is running short, and these signs are expensive. Figure out the
minimum set of signs you need to purchase to show any score that is possible to achieve during the
game. Notethatyouwon’tneedany9signs,asany6signcanbeturnedupside-downtomakea9.

## Input
Thefirstlineofinputcontainstwointegersmandn, wherem(1 m 1018)isthemaximumscore
≤ ≤
value,andn(1 n 10)isthenumberofdifferentwaysofscoring. Thisisfollowedbynlines,each
≤ ≤
containinganintegerp(1 p 1000), whichisthenumberofpointsawardedforatypeofactionin
≤ ≤
thegame. Notwotypesofactionareawardedthesamenumberofpoints.

## Output
For each digit from 0 to 8 in increasing order, output two integers: the digit and the number of signs
withthatdigitthatyouneedtopurchase. Omitdigitswherethenumberofsignsneededis0.
49thICPCWorldChampionshipProblemH:ScoreValues©ICPCFoundation 15
Sample Input 1 Sample Output 1
1000 4 0 3
60 1 1
100 2 3
222 3 1
650 4 3
5 1
6 3
7 2
8 3
Sample Input 2 Sample Output 2
967 1 0 1
1000 6 2
7 1
49thICPCWorldChampionshipProblemH:ScoreValues©ICPCFoundation 16

## Constraints
(Not found)
