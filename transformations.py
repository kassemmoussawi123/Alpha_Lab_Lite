import numpy as np 
import pandas as pd

def Fetch(datasource):
    // pull_data()
    prices_df = pd.read_csv("data/fetch_transformation_data.csv")
    // validate if prices_df is valid
    target_row = prices_df[prices_df["label"] == datasource]
    
    if target_row.empty:
        return None
    //instead of 1 say : skip index
    series = target_row.values[0][1:]

    return list(series)
    
def simpleMovingAverage(A,window):
    B = [] #output list I prefer to a a better naming
    for i in range(len(A)): 
        if i < window-1: 
            B.append(np.nan)# windown.size> current.index ,so we cant calculate it . 
        else: 
            B.append(sum(A[i-window+1:i+1])/window) #average B = ∑A[i-window+1:i+1]/window
    return B

def ExponentialMovingAverage(alpha, A):
    // validate length of A
    B = [A[0]] # t = 0

    for i in range(1, len(A)):
        value = alpha*A[i] + (1-alpha)*B[i-1]#alpha × A[t] + (1 − alpha) × B[t − 1]
        B.append(value)

    return B
    
def RateOfChange(A , period): 
   B = []
   for i in range(len(A)): 
       if (i - period)<0: 
           B.append(np.nan)
       elif (A[i-period] == 0): 
           B.append(np.nan)
       else: 
           B.append((A[i] - A[i-period])/A[i-period]) #A[t] - A[t− period])/A[t− period]
   return B

def CrossAbove(A1, A2):
    """we need it here 
    entry_signals = CrossAbove{}{slow_sma, fast_sma}
    #exit_signals = CrossAbove(}{fast_sma, slow_sma}"""
    B = [0]      # first point has no previous point

    minimum_length = min(len(A1), len(A2))

    for i in range(1, minimum_length):
        if A1[i-1] < A2[i-1] and A1[i] > A2[i]:
           
            B.append(1)  #B[t] = A1[t − 1] < A2[t − 1] and A1[t] > A2[t]
        else:
            B.append(0)

    return B

def ConstantSeries(A, k):
    B = [k for i in range (len(A))] #B[t]= k for all t
    return  B

def PortfolioSimulation(balance, price, entry, exit):
    n = len(price)
    positions_held = 0
    portfolio = [0] * n

    for i in range(n):
        if exit[i] == 1:
            balance += positions_held * price[i]
            positions_held = 0

        elif entry[i] == 1:
            positions_held += 1
            balance -= price[i]

        portfolio[i] = balance + positions_held * price[i]

    return portfolio
