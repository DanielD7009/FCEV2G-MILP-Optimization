#!/usr/bin/env python
# coding: utf-8

# In[34]:


import gurobipy as gp
from gurobipy import GRB
import pandas as pd
import numpy as np
import timeit
# all monetary numbers are in USD


# In[62]:


def read_data(data_filename,Print_Data=True,Print_Length=True):
    ### this function extract the second column of a datasheet which has "date, price" in the first row as value names
    ## reading csv file from the same directory
    csvFile = pd.read_csv(data_filename)
    ## creating a DataFrame
    Data = pd.DataFrame(csvFile)
    if Print_Data:
        print(Data)
    Data_List=list(Data.iloc[:,1])
    #print(Data_List)
    if Print_Length:
        print(len(Data_List))
    return Data_List


def solving(price_filename, traffic_filename,carbon_filename,
            Efficiency_H2E,Efficiency_E2H
            ,Delivery_Cost_Market_Hydrogen,Production_Cost_Market_Hydrogen
            ,Max_input_electrolyzer, Max_output_fuelcell, number_of_vehicles
            ,Max_hydrogen_tank
            ,filename="sheeeet.csv"
            ):
    ### this function is the main function of solving the MILP problem. 

    EP=read_data(price_filename)#load electricity price
    traffic=read_data(traffic_filename)#laod traffic constraint
    carbon=read_data(carbon_filename)#load electricity carbon intensity

    for i in range(len(EP)): #convert the electricity price from CAD to USD
        EP[i]=EP[i]*0.75
    
    m=gp.Model('MILP') #merely a name 

    ### decision varibales; units: kW, kWh
    P_G2E=m.addVars(len(EP),name='P_G2E',lb=0,vtype=GRB.INTEGER)#power of electricity generation
    vehicles=m.addVars(len(EP),name='vehicles',lb=0,ub=number_of_vehicles,vtype=GRB.INTEGER)
    P_FC2G=m.addVars(len(EP),name='P_FC2G',lb=0,vtype=GRB.INTEGER)
    P_E2HT=m.addVars(len(EP),name='P_E2HT',lb=0,vtype=GRB.INTEGER)
    P_HT2FC=m.addVars(len(EP),name='P_HT2FC',lb=0,vtype=GRB.INTEGER)
    P_MH2FC=m.addVars(len(EP),name='P_MH2FC',lb=0,vtype=GRB.INTEGER)
    Reserve_HT=m.addVars(len(EP),name='Reserve_HT',lb=0,ub=Max_hydrogen_tank*1000,vtype=GRB.INTEGER)
    obj=m.addVar(name='obj',lb=0,vtype=GRB.CONTINUOUS)
    ### constarints
    ## traffic constraint 1
    m.addConstrs(P_FC2G[i]==Max_output_fuelcell*vehicles[i]*1000 for i in range(len(EP)))
    ##conversion constraints
    m.addConstrs(P_E2HT[i]<=(P_G2E[i]*Efficiency_E2H) for i in range(len(EP)))
    m.addConstrs(P_E2HT[i]>=(P_G2E[i]*Efficiency_E2H-1) for i in range(len(EP)))
    m.addConstrs(P_FC2G[i]<=(P_HT2FC[i]+P_MH2FC[i])*Efficiency_H2E for i in range(len(EP)))
    m.addConstrs(P_FC2G[i]>=((P_HT2FC[i]+P_MH2FC[i])*Efficiency_H2E-1) for i in range(len(EP)))
    
    ##reserve constraints
    for i in range(len(EP)):
        m.addConstr(sum(P_E2HT[j]-P_HT2FC[j] for j in range(i+1))==Reserve_HT[i])
        
    ##power constaints
    m.addConstrs(P_G2E[i]<=Max_input_electrolyzer*1000 for i in range(len(EP)))
    m.addConstrs(P_FC2G[i]<=Max_output_fuelcell*number_of_vehicles*1000 for i in range(len(EP)))
    ##traffic Constraint 2
    for i in range(len(EP)):
        if i%24 not in list(range(7,12))+list(range(16,21)): # 7：00 - 11:00 & 16:00 - 21:00
            m.addConstr(vehicles[i]==0) # the electricity generation phase must be during the rush hours
    for i in range(len(EP)):
            m.addConstr(vehicles[i]<=traffic[i]) # availible vehicles is limited by the traffic volume
   ## objective function
    obj_fn=sum((EP[i]*P_FC2G[i]
                -EP[i]*P_G2E[i]
                -P_MH2FC[i]*(Delivery_Cost_Market_Hydrogen+Production_Cost_Market_Hydrogen)
               )/1000
               +
               (-(carbon[i]*P_FC2G[i]
                -carbon[i]*P_G2E[i]
                -P_MH2FC[i]*20
               )*0.05*0.75*0/1000
               ) for i in range(len(EP)))
    #-refrigeration_energy_consumption(number_of_vehicles)[1]*EP[i]*one_zero(P_HT2FC[i]+P_MH2FC[i])
    # 30 kg H2 = 1 MWh H2
    ### unit: USD $
    ### objective function = (profit of selling electricity from fuel cells)
    ### - (cost of buying electricity into fuel cell) 
    ### - (cost of buying markey hydrogen)
    ### - (cost of energy resulting from using hydrogen: compression and regrigeration)
    ### - (electricity cost of overhead refrigeration)
    #print('compressor energy consumption (kw/kg):',compressor_energy_consumption(number_of_vehicles))
    #print('refrigeration energy consumption (kw/kg):',refrigeration_energy_consumption(number_of_vehicles)[0])
    #print('overhead refrigeration energy consumption (kw):',refrigeration_energy_consumption(number_of_vehicles)[1])
    m.setObjective(obj_fn,GRB.MAXIMIZE)
    m.printStats()
    #solve
    try:
        m.optimize()
    except gp.GurobiError:
        print("optimization failed due to non-convexity")

    with open(filename,mode='w',newline='') as sheet:
        sheet.write('name'+','+'value'+'\n')
        for v in m.getAttr('x',m.getVars()):
            sheet.write(str(v)+'\n')
          
    File_Reread = pd.read_csv(filename)
    Variables = pd.DataFrame(File_Reread)

# calculate the overhead refrigeration, which only occurs in each hour when hydrogen is consumed

    with open(filename,mode='w',newline='') as sheet:
        sheet.write('G2E,vechiles,FC2G,E2HT,HT2FC,MH2FC,Reserve_HT\n')
        for i in range(len(EP)):
            sheet.write(str(Variables.iloc[i,0])+','
                        +str(Variables.iloc[i+len(EP),0])+','
                        +str(Variables.iloc[i+len(EP)*2,0])+','
                        +str(Variables.iloc[i+len(EP)*3,0])+','
                        +str(Variables.iloc[i+len(EP)*4,0])+','
                        +str(Variables.iloc[i+len(EP)*5,0])+','
                        +str(Variables.iloc[i+len(EP)*6,0])+','+'\n')
    objective_solution=sum(((EP[i]*Variables.iloc[i+len(EP)*2,0]
                -EP[i]*Variables.iloc[i,0]
                -Variables.iloc[i+len(EP)*5,0]*(Delivery_Cost_Market_Hydrogen+Production_Cost_Market_Hydrogen)
               )/1000
               ) for i in range(len(EP)))
    return objective_solution


# In[63]:


Max_input_electrolyzer=1 # MW
Max_output_fuelcell=0.4 # MW
number_of_vehicles=8
Max_hydrogen_tank=10 # MWh
Efficiency_H2E=0.5
Efficiency_E2H=0.6
directory='~/projects/def-x369wu/z69ding/May7/V2G-main/'
Penetration='100'
Willingness='6'
market_hydrogen_cost=5 # USD/kg

price_filename=directory+'sheets/price/Alberta_Price_2022.csv'
traffic_filename=directory+'sheets/traffic/Alberta-Calgary-Northbound-2022-Randomized.csv'
#traffic_filename=directory+'sheets/traffic/Alberta-Edmonton-South-01-12-2022-'+Penetration+'-'+Willingness+'-3'+'.csv'
carbon_filename=directory+'sheets/carbon/Alberta_Carbon_2022.csv'
filename="sheets/results/Revenue_AB_BaseCase2022"+".csv"
# In[64]:


X=solving(price_filename=price_filename, traffic_filename=traffic_filename, carbon_filename=carbon_filename
    ,Efficiency_H2E=Efficiency_H2E,Efficiency_E2H=Efficiency_E2H
    ,Delivery_Cost_Market_Hydrogen=0,Production_Cost_Market_Hydrogen=market_hydrogen_cost*30
    ,Max_input_electrolyzer=Max_input_electrolyzer, Max_output_fuelcell=Max_output_fuelcell, number_of_vehicles=number_of_vehicles
    ,Max_hydrogen_tank=Max_hydrogen_tank
    ,filename=filename)

print('result:',X)
