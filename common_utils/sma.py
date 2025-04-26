import os,sys
import pandas as pd

# Determine trend based on SMA_5 and SMA_21
def get_trend_5_21_sma(row):
    if pd.isna(row["SMA_5"]) or pd.isna(row["SMA_21"]):
        return None  # Avoid trends for NaN values
    if row["SMA_5"] > row["SMA_21"]:
        return "UP"
    elif row["SMA_5"] < row["SMA_21"]:
        return "DOWN"
    else:
        return "NEUTRAL"


def get_sma_trend(data):
    ''' Get SMA and add it as column in Data Frame  and return last trend'''

    df = pd.DataFrame(data)

    # Calculate moving averages
    if 'Close' in df.keys() :
        close = 'Close'
    else:
        close = 'close'

    df["SMA_5"] = df[close].rolling(window=5).mean()
    df["SMA_7"] = df[close].rolling(window=7).mean()
    df["SMA_21"] = df[close].rolling(window=21).mean()
    df["5_21_SMA_Trend"] = df.apply(get_trend_5_21_sma, axis=1)

    return df

def main(file_name):
    # Given a DF with OHLC , created supertrend and write to a file prefixed with supertread_
    if os.path.exists(file_name):
        data = pd.read_csv(file_name)
        data.columns = data.columns.str.lower()
        s_file = os.path.basename(f"{file_name}")
        s_file = f"sma_{s_file}"
        s_data = get_sma_trend(data)
        s_data.to_csv(s_file, index=False)
        print(f"Filename .. {s_file}")
        return s_file
    else :
        sys.exit("Data file is needed to process ")

if __name__ == '__main__':
    main('supertrend_nifty50_2022_260_data.csv')

