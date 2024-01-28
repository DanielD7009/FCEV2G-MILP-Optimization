# FCEV2G operational optimization (buy-sell model)
This program is a MILP (mixed linear linear programmiing). It optimizes the operation of an FCEV2G (fuel cell electric vehicle to grid) station by determining the best time and scale of buying and selling energy to achieve the highest profit.

The data inputs are traffic file, electricity price file, and electricity carbon intensity file

Variations of this model includes:

 1.change the optimization target from profit to carbon emission reduction

2. include carbon tax into profit

3. sensitivity analysis by changing parameters including effciencies and staion size
   
(the codes here are originally designed to run on Compute Canada)
