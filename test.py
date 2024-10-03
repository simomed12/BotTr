import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

# Initialiser la connexion à MetaTrader 5
if not mt5.initialize():
    print("Échec de l'initialisation")
    mt5.shutdown()
    exit()

# Sélectionner l'instrument financier
symbol = 'XAUUSD'
timeframe = mt5.TIMEFRAME_M15

# Vérifier si le symbole est disponible
symbol_info = mt5.symbol_info(symbol)
if symbol_info is None:
    print(f"Symbole {symbol} non trouvé")
    mt5.shutdown()
    exit()

if not symbol_info.visible:
    if not mt5.symbol_select(symbol, True):
        print(f"Impossible de sélectionner {symbol}")
        mt5.shutdown()
        exit()

# Définir la période pour la semaine dernière
end_time = datetime.now()
start_time = end_time - timedelta(days=7)

# Récupérer les données historiques
rates = mt5.copy_rates_range(symbol, timeframe, start_time, end_time)
if rates is None or len(rates) == 0:
    print("Aucune donnée n'a été récupérée")
    mt5.shutdown()
    exit()

# Convertir les données en DataFrame pandas
data = pd.DataFrame(rates)
data['time'] = pd.to_datetime(data['time'], unit='s')

# Calculer les indicateurs techniques
data['EMA_50'] = ta.ema(data['close'], length=50)
data['EMA_200'] = ta.ema(data['close'], length=200)
data['RSI'] = ta.rsi(data['close'], length=14)
bb = ta.bbands(data['close'], length=20)
data = pd.concat([data, bb], axis=1)

# Initialiser les variables pour le backtesting
initial_balance = 10000  # Solde initial fictif
balance = initial_balance
positions = []
trade_log = []

# Paramètres de la stratégie
lot = 0.1
sl_points = 500  # Stop Loss en points
tp_points = 1000  # Take Profit en points

# Simulation du backtesting
for i in range(200, len(data)):
    current_data = data.iloc[i]
    price = current_data['close']
    time_stamp = current_data['time']
    
    # Vérifier s'il y a une position ouverte
    if not positions:
        # Conditions d'achat
        if (current_data['close'] > current_data['EMA_200'] and
            current_data['EMA_50'] > current_data['EMA_200'] and
            current_data['RSI'] > 50 and
            current_data['close'] <= current_data['BBL_20_2.0']):
            
            # Ouvrir une position longue
            entry_price = price
            sl = entry_price - sl_points * symbol_info.point
            tp = entry_price + tp_points * symbol_info.point
            positions.append({'type': 'buy', 'entry_price': entry_price, 'sl': sl, 'tp': tp, 'entry_time': time_stamp})
            print(f"Position d'achat ouverte à {entry_price} le {time_stamp}")
        
        # Conditions de vente
        elif (current_data['close'] < current_data['EMA_200'] and
              current_data['EMA_50'] < current_data['EMA_200'] and
              current_data['RSI'] < 50 and
              current_data['close'] >= current_data['BBU_20_2.0']):
            
            # Ouvrir une position courte
            entry_price = price
            sl = entry_price + sl_points * symbol_info.point
            tp = entry_price - tp_points * symbol_info.point
            positions.append({'type': 'sell', 'entry_price': entry_price, 'sl': sl, 'tp': tp, 'entry_time': time_stamp})
            print(f"Position de vente ouverte à {entry_price} le {time_stamp}")
    else:
        # Gérer la position ouverte
        position = positions[0]
        trade_closed = False

        # Vérifier le stop loss
        if position['type'] == 'buy' and price <= position['sl']:
            profit = (position['sl'] - position['entry_price']) * lot * 100
            balance += profit
            trade_log.append({'entry_time': position['entry_time'], 'exit_time': time_stamp,
                              'type': 'buy', 'entry_price': position['entry_price'], 'exit_price': position['sl'], 'profit': profit})
            positions.pop()
            trade_closed = True
            print(f"Position d'achat fermée par SL à {position['sl']} le {time_stamp}")
        elif position['type'] == 'sell' and price >= position['sl']:
            profit = (position['entry_price'] - position['sl']) * lot * 100
            balance += profit
            trade_log.append({'entry_time': position['entry_time'], 'exit_time': time_stamp,
                              'type': 'sell', 'entry_price': position['entry_price'], 'exit_price': position['sl'], 'profit': profit})
            positions.pop()
            trade_closed = True
            print(f"Position de vente fermée par SL à {position['sl']} le {time_stamp}")
        
        # Vérifier le take profit
        if not trade_closed:
            if position['type'] == 'buy' and price >= position['tp']:
                profit = (position['tp'] - position['entry_price']) * lot * 100
                balance += profit
                trade_log.append({'entry_time': position['entry_time'], 'exit_time': time_stamp,
                                  'type': 'buy', 'entry_price': position['entry_price'], 'exit_price': position['tp'], 'profit': profit})
                positions.pop()
                print(f"Position d'achat fermée par TP à {position['tp']} le {time_stamp}")
            elif position['type'] == 'sell' and price <= position['tp']:
                profit = (position['entry_price'] - position['tp']) * lot * 100
                balance += profit
                trade_log.append({'entry_time': position['entry_time'], 'exit_time': time_stamp,
                                  'type': 'sell', 'entry_price': position['entry_price'], 'exit_price': position['tp'], 'profit': profit})
                positions.pop()
                print(f"Position de vente fermée par TP à {position['tp']} le {time_stamp}")

# Fermer toute position restante à la fin de la période
if positions:
    position = positions[0]
    current_price = data.iloc[-1]['close']
    if position['type'] == 'buy':
        profit = (current_price - position['entry_price']) * lot * 100
    else:
        profit = (position['entry_price'] - current_price) * lot * 100
    balance += profit
    trade_log.append({'entry_time': position['entry_time'], 'exit_time': data.iloc[-1]['time'],
                      'type': position['type'], 'entry_price': position['entry_price'], 'exit_price': current_price, 'profit': profit})
    positions.pop()
    print(f"Position fermée à la fin de la période à {current_price}")

# Résultats du backtesting
df_trades = pd.DataFrame(trade_log)
print("\nRésumé des transactions :")
print(df_trades)

profit_total = df_trades['profit'].sum()
print(f"\nProfit total : {profit_total}")
print(f"Solde final : {balance}")

# Visualisation du solde au fil du temps
df_trades['balance'] = initial_balance + df_trades['profit'].cumsum()
plt.figure(figsize=(10,6))
plt.plot(df_trades['exit_time'], df_trades['balance'], marker='o')
plt.xlabel('Date')
plt.ylabel('Solde')
plt.title('Évolution du solde au fil des transactions')
plt.grid(True)
plt.show()
