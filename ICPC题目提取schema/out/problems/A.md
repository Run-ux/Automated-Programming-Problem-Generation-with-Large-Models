# A. A-Skew-ed Reasoning

## Description
The following is based on a true story – the names have been changed because...well, because you
alwayschangenamesinstorieslikethisone.
Professor Taylor Swift is grading a homework assignment on integer skew heaps. A skew heap is a
binarytreewithanintegerstoredineachnodesuchthatthevalueinanynodeislessthanorequaltothe
values in any of its children. Note that the skew heap need not be a perfect binary tree; that is, the left
and/orrightsubtreeofanynodemaybeempty.
InsertingavaluexintoaskewheapH isdoneusingthefollowingrecursiveprocedure:
• IfH isempty,makeH askewheapconsistingofasinglenodecontainingx.
• Otherwise,lety bethevalueintherootofH.
– Ify < x,swapthetwochildrenoftherootandrecursivelyinsertxintothenewleftsubtree.
– Ify x,createanewnodewithvaluexandmakeH theleftsubtreeofthisnode.
≥
4 4
9 5 5 9
20 25 6 11 7 6 20 25
17 11
17
FigureA.1: Exampleofinsertingthevalue7intoaskewheap. Thenodesstoring4and5
(markedinblue)havetheirchildrenswapped,whilethenodestoring11becomestheleft
childofthenewlyinsertednode(markedinred).
Now, back to Professor Swift. The homework problem she has assigned asks the students to show the
heap that results from inserting a given permutation of the numbers from 1 to n, in the given order,
into an empty heap. Surprisingly, some of the students have wrong answers! That got Professor Swift
wondering: Foragivenheap,isthereaninputpermutationthatwouldhaveproducedthisheap? Andif
so,whatarethelexicographicallyminimalandmaximalsuchinputpermutations?

## Input
The first line of input contains an integer n (1 n 2 105), the number of nodes in the tree. These
≤ ≤ ·
nodes contain the numbers from 1 to n exactly. This is followed by n lines, the ith of which contains
twointegersℓ andr (i < ℓ norℓ = 0;i < r norr = 0),describingthevaluesoftheleftand
i i i i i i
≤ ≤
right children of the node storing i, where a value of 0 is used to indicate that the corresponding child
doesnotexist. Itisguaranteedthatthisdatadescribesabinarytree.
49thICPCWorldChampionshipProblemA:A-Skew-edReasoning©ICPCFoundation 1

## Output
Outputthelexicographicallyminimalinputpermutationthatproducesthegiventreeundertheinsertion
methodforskewheaps,followedbythelexicographicallymaximalsuchinputpermutation. Theseper-
mutationsmaycoincide,inwhichcaseyoustillneedtooutputboth. Ifnoinputpermutationproducing
thegiventreeexists,outputimpossible.
Sample Input 1 Sample Output 1
7 1 3 2 7 5 6 4
2 3 7 1 5 3 2 6 4
4 5
6 7
0 0
0 0
0 0
0 0
Sample Input 2 Sample Output 2
2 impossible
0 2
0 0
Sample Input 3 Sample Output 3
3 2 3 1
2 0 3 2 1
3 0
0 0
49thICPCWorldChampionshipProblemA:A-Skew-edReasoning©ICPCFoundation 2

## Constraints
(Not found)
