import warnings
import os
import pandas as pd
import pandas_ta as ta
import sys
from datetime import time
import config

warnings.filterwarnings('ignore')

# Set print display preferance
pd.set_option('display.max_rows',None)
pd.set_option('display.width', None)


def supertrend(df, atr_multiplier=3,period = 15):
    # Calculate the Upper Band(UB) and the Lower Band(LB)
    # Formular: Supertrend =(High+Low)/2 + (Multiplier)∗(ATR)
    ATR = f"atr_{atr_multiplier}"
    UPPERBAND = f"upperband_{atr_multiplier}"
    LOWERBAND = f"lowerband_{atr_multiplier}"

    current_average_high_low = (df['high']+df['low'])/2
    df[ATR] = ta.atr(df['high'], df['low'], df['close'], period)
    df.dropna(inplace=True)
    df['basicUpperband'] = current_average_high_low + (atr_multiplier * df[ATR])
    df['basicLowerband'] = current_average_high_low - (atr_multiplier * df[ATR])
    first_upperBand_value = df['basicUpperband'].iloc[0]
    first_lowerBand_value = df['basicLowerband'].iloc[0]
    upperBand = [first_upperBand_value]
    lowerBand = [first_lowerBand_value]

    for i in range(1, len(df)):
        if df['basicUpperband'].iloc[i] < upperBand[i-1] or df['close'].iloc[i-1] > upperBand[i-1]:
            upperBand.append(df['basicUpperband'].iloc[i])
        else:
            upperBand.append(upperBand[i-1])

        if df['basicLowerband'].iloc[i] > lowerBand[i-1] or df['close'].iloc[i-1] < lowerBand[i-1]:
            lowerBand.append(df['basicLowerband'].iloc[i])
        else:
            lowerBand.append(lowerBand[i-1])

    df[UPPERBAND] = upperBand
    df[LOWERBAND] = lowerBand
    df.drop(['basicUpperband', 'basicLowerband',], axis=1, inplace=True)
    return df

def generate_signals(df,atr):
    # Intiate a signals list
    SIGNALS = f"signals_{atr}"
    UPPERBAND = f"upperband_{atr}"
    LOWERBAND = f"lowerband_{atr}"
    signals = [0]

    # Loop through the dataframe
    for i in range(1 , len(df)):

        if df['close'].iloc[i] > df[UPPERBAND].iloc[i]:
            signals.append(1)
        elif df['close'].iloc[i] < df[LOWERBAND].iloc[i]:
            signals.append(-1)
        else:
            signals.append(signals[i-1])

    # Add the signals list as a new column in the dataframe
    df[SIGNALS] = signals
    #df['signals'] = df["signals"].shift(1) #Remove look ahead bias
    return df


def get_atr(df,idx):
    signal_cols = [col for col in df.columns if col.startswith('atr_')]
    atr = df.loc[idx,signal_cols[-1]] 
    dtime = df.loc[idx, 'datetime']
    _open = df.loc[idx, 'open']
    _close = df.loc[idx, 'close']
    return int(atr),dtime,_open,_close

def detect_entry_exit_signals_from_csv(df):
    # Step 1: Load CSV
    #df = pd.read_csv(file_path)

    # Step 2: Identify 'signal_' columns
    first_candle = False
    ok_for_entry  = True
    signal_cols = [col for col in df.columns if col.startswith('signals_')]

    if len(signal_cols) < 1:
        raise ValueError("No 'signals_' columns found.")

    # Step 3: Check all 'signal_' columns have at least 2 non-null values
    for col in signal_cols:
        if df[col].dropna().shape[0] < 2:
            raise ValueError(f"Column '{col}' has fewer than two values.")

    # Step 4: Entry/Exit signal logic
    entry_signals = []
    exit_signals = []
    previous_state = None  # Track previous consensus (1 or -1)

    for idx, row in df[signal_cols].iterrows():
        values = row.values
        unique_values = set(values)

        if len(unique_values) == 1 and list(unique_values)[0] in [1, -1]:
            current_state = list(unique_values)[0]
        else:
            current_state = None

        atr, dtime,o,c = get_atr(df,idx)

        dt = pd.Timestamp(dtime)
        cutoff = time(11, 30)
        first_candle_time = time(9, 15)

        # Cut off time is 11:30 AM
        if dt.time() > cutoff:
            ok_for_entry  = False
        else:
            ok_for_entry  = True

        # FIrst candle at 9:15 AM 
        first_candle = False
        if  dt.time() == first_candle_time :
            # Only in case of GAP up or GAP down by 30+ points 
            #gap = ' '
            if not idx == 0 :
                atr_1, dtime_1,op,close = get_atr(df,idx-1)
                if int(o) > int(close) + 30 :
                    #gap = 'UP'
                    first_candle = True
                elif int(o) < int(close) - 30 :
                    #gap = 'DOWN'
                    first_candle = True


        if ( previous_state is None or first_candle )  and current_state is not None and ok_for_entry:

            if current_state == 1 and atr > 21 :
                #print(dtime, 'ENTRY_BULLISH', atr,c,previous_state,current_state)
                entry_signals.append('ENTRY_BULLISH')
            elif  current_state == -1 and atr > 21:
                #print(dtime, 'ENTRY_BEARISH', atr,c,previous_state,current_state)
                entry_signals.append('ENTRY_BEARISH')
            else:
                entry_signals.append(None)

            exit_signals.append(None)
            previous_state = current_state
        elif previous_state is not None and current_state != previous_state:
            entry_signals.append(None)
            exit_signals.append('EXIT')
            #print(dtime, 'EXIT', atr,c)
            previous_state = None
        else:
            entry_signals.append(None)
            exit_signals.append(None)

    # Step 5: Save to file
    df['entry_flag'] = entry_signals
    df['exit_flag'] = exit_signals
    #df.to_csv(file_path, index=False)
    #print(f"Updated CSV saved: {file_path}")
    return df


# Get SuperTrend and attach supertrend signals to given dataframe and return
def get_supertrend(data):
    #volatility = 3.5
    len_volatily = {
            '10':1,
            '11':2,
            '12':3
            }
    for key in len_volatily.keys():
        atr = len_volatily[key]
        ATR = f"atr_{atr}"
        UPPERBAND = f"upperband_{atr}"
        LOWERBAND = f"lowerband_{atr}"
        length = int(key)
        volatility = float(len_volatily[key])
        data.columns = data.columns.str.lower()
        # Apply supertrend formula
        supertrend_data = supertrend(data, volatility,length)
    
        # Generate the Signals
        supertrend_positions = generate_signals(supertrend_data,volatility)
        #supertrend_positions.drop([UPPERBAND,LOWERBAND], axis=1, inplace=True)
    supertrend_positions = detect_entry_exit_signals_from_csv(supertrend_positions)
    return supertrend_positions

def main(data):
    file_name = 'hourly_candle.csv'
    data.columns = data.columns.str.lower()
    s_file = os.path.basename(f"{file_name}")
    s_file = f"supertrend_{s_file}"
    #if os.path.exists(s_file):
    #    sys.exit(f" File {s_file} already exists , delete it if you want it to be recreated")
    s_data = get_supertrend(data)
    s_data.to_csv(s_file, index=False)
    return s_file

if __name__ == '__main__':
    # Given a DF with OHLC , created supertrend and write to a file prefixed with supertread_
    main('nifty50_2022_260_data.csv') 
