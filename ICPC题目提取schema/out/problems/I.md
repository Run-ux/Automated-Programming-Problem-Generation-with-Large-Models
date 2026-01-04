# I. Slot Machine

## Description
Imperial Chance & Play Casino offers games using a slot machine that has n wheels arranged next to
eachother. Eachofthewheelshasndistinctsymbolsonit,andthesesymbolsappearinthesameorder
on each wheel. Each wheel shows one of its symbols through a window on the front of the machine,
whichresultsinasequenceofnsymbolsbeingshownnexttoeachother.
FigureI.1: TheinitialconfigurationinSampleInteraction1.
You are standing behind the machine and notice that a maintenance panel has been left open. When
you stick your hand inside, you are able to secretly rotate any of the wheels by any number of steps,
thuschangingthesymbolshownonthatwheel. Youwanttowinajackpot,whichwillhappenifallthe
wheels show the same symbol at the same time. Unfortunately, you cannot see the symbols from your
position,soyouaskedyourgoodfriendtohelpyou. Thefriendisstandinginfrontofthemachineand
she tells you the number of distinct symbols in the sequence she can currently see. Can you win the
jackpotbymanipulatingthewheelsifyourfriendupdatestheinformationaftereveryactionyoumake?
Interaction
Thefirstlineofinputcontainsanintegern(3 n 50),givingthenumberofwheelsandsymbolsin
≤ ≤
themachine.
Interaction then proceeds in rounds. In each round, one line of input becomes available, containing an
integer k (1 k n), the number of distinct symbols in the current sequence. If k > 1, output two
≤ ≤
integers i and j (1 i n; 109 j 109), representing your action: rotating the ith wheel by
≤ ≤ − ≤ ≤
j positions, where negative numbers indicate rotating in the opposite direction. Otherwise, if k = 1,
indicatingthatallwheelsshowthesamesymbol,yourprogrammustexitwithoutprintingmoreoutput.
At most 10000 actions are allowed – if your submission uses more rounds, it will not be accepted. It
isguaranteedthattheinitialconfigurationofwheelsdoesnotalreadyhaveallwheelsshowingthesame
symbol(k > 1inthefirstround).
Thejudgeprogramwillnotbehaveinanadversarialway,whichmeanstheinitialconfigurationisfixed
beforethefirstaction.
Atestingtoolisprovidedtohelpyoudevelopandtestyoursolution.
49thICPCWorldChampionshipProblemI:SlotMachine©ICPCFoundation 17
Read Sample Interaction 1 Write
5
4
1 1
3
4 2
3
3 1
3
3 1
2
5 4
1
Read Sample Interaction 2 Write
3
3
2 -1
2
3 -1
2
2 -1
1
49thICPCWorldChampionshipProblemI:SlotMachine©ICPCFoundation 18

## Input
(Not found)

## Output
(Not found)

## Constraints
(Not found)
