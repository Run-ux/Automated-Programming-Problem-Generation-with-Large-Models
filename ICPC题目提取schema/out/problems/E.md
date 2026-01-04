# E. Delivery Service

## Description
The Intercity Caspian Package Company (ICPC) is starting a delivery service which will deliver pack-
agesbetweenvariouscitiesneartheCaspianSea. Thecompanyplanstohirecourierstocarrypackages
betweenthesecities.
Eachcourierhasahomecityandadestinationcity,andallcouriershaveexactlythesametravelsched-
ule: They leave their home city at 9:00, arrive at their destination city at 12:00, leave their destination
city at 14:00 and return to their home city at 17:00. While couriers are in their home or destination
cities, they can receivepackages from and/or deliver packages tocustomers. They can alsohand off to
orreceivepackagesfromothercourierswhoareinthatcityatthesametime. SinceICPCisapersonal
service,packagesareneverleftinwarehousesorotherfacilitiestobepickeduplater–unlessthepack-
agehasreacheditsdestination,couriershavetoeitherkeepthepackagewiththemselves(duringtheday
orduringthenight),orhanditofftoanothercourier.
The company will direct the couriers to hand off packages in such a way that any package can always
bedeliveredtoitsdestination. Orsoitishoped! We’llsaythattwocitiesuandv areconnected ifitis
possible to deliver a package from city u to city v as well as from v to u. To estimate the efficiency of
their hiring process, the company would like to find, after each courier is hired, the number of pairs of
cities(u,v)thatareconnected(1 u < v n).
≤ ≤

## Input
Thefirstlineofinputcontainstwointegersnandm,wheren(2 n 2 105)isthenumberofcities,
≤ ≤ ·
andm(1 m 4 105)isthenumberofcouriersthatwillbehired. Couriersarenumbered1tom,in
≤ ≤ ·
the order they are hired. This is followed by m lines, the ith of which contains two distinct integers a
i
andb (1 a ,b n),denotingthehomeanddestinationcities,respectively,forcourieri.
i i i
≤ ≤

## Output
Output m integers, denoting the number of pairs of connected cities after hiring the first 1,2,...,m
couriers.
49thICPCWorldChampionshipProblemE:DeliveryService©ICPCFoundation 9
Sample Input 1 Sample Output 1
4 4 1
1 2 2
2 3 4
4 3 6
4 2
ExplanationofSample1:
1. Afterthefirstcourierishired,cities1and2areconnected.
2. Afterthesecondcourierishired, cities2and3areconnected. Note, however, thatcities1and3
arestillnotconnected. Eventhoughthere’sacouriermovingbetweencities1and2,andacourier
movingbetweencities2and3,theynevermeeteachother.
3. Afterthethirdcourierishired,cities3and4areconnectedandcities2and4areconnected. For
example,onewaytodeliverapackagefromcity2tocity4is:
• handittocourier2incity2at19:00;
• the next day, courier 2 arrives in city 3 at 12:00, and hands the package to courier 3 who is
alsoincity3;
• at18:00,courier3deliversthepackagetocity4.
4. Afterthefourthcourierishired,allsixpairsofcitiesareconnected.
49thICPCWorldChampionshipProblemE:DeliveryService©ICPCFoundation 10

## Constraints
(Not found)
