import warnings
import os
import pandas as pd
import pandas_ta as ta
import sys
warnings.filterwarnings('ignore')

# Set print display preferance
pd.set_option('display.max_rows',None)
pd.set_option('display.width', None)


def supertrend(df, atr_multiplier=3):
    # Calculate the Upper Band(UB) and the Lower Band(LB)
    # Formular: Supertrend =(High+Low)/2 + (Multiplier)∗(ATR)
    current_average_high_low = (df['high']+df['low'])/2
    df['atr'] = ta.atr(df['high'], df['low'], df['close'], period=15)
    df.dropna(inplace=True)
    df['basicUpperband'] = current_average_high_low + (atr_multiplier * df['atr'])
    df['basicLowerband'] = current_average_high_low - (atr_multiplier * df['atr'])
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

    df['upperband'] = upperBand
    df['lowerband'] = lowerBand
    df.drop(['basicUpperband', 'basicLowerband',], axis=1, inplace=True)
    return df

def generate_signals(df):
    # Intiate a signals list
    signals = [0]

    # Loop through the dataframe
    for i in range(1 , len(df)):

        if df['close'].iloc[i] > df['upperband'].iloc[i]:
            signals.append(1)
        elif df['close'].iloc[i] < df['lowerband'].iloc[i]:
            signals.append(-1)
        else:
            signals.append(signals[i-1])

    # Add the signals list as a new column in the dataframe
    df['signals'] = signals
    #df['signals'] = df["signals"].shift(1) #Remove look ahead bias
    return df

# Get SuperTrend and attach supertrend signals to given dataframe and return
def get_supertrend(data):
    volatility = 3

    data.columns = data.columns.str.lower()
    # Apply supertrend formula
    supertrend_data = supertrend(df=data, atr_multiplier=volatility)

    # Generate the Signals
    supertrend_positions = generate_signals(supertrend_data)
    return supertrend_positions

def main(data):
    #data = pd.read_csv(file_name)
    #print('-'*80)
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
