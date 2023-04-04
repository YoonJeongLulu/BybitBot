from bybit_cycle import BybitCycle

if __name__ == "__main__":

    # insert your api_key and secret
    api_key = ""
    api_secret = ""

    btc_long = BybitCycle(symbol="BTCUSD",
                          position="long",
                          contracts=10,
                          api_key=api_key,
                          api_secret=api_secret,
                          is_prod=False)

    while True:
        btc_long.set_logger()
        btc_long.switch_to_isolated()
        btc_long.cycle()
