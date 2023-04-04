from bybit_cycle import BybitCycle

if __name__ == "__main__":
    
    # insert your api_key and secret
    api_key = ""
    api_secret = ""

    xrp_long = BybitCycle(symbol="XRPUSD",
                          position="long",
                          contracts=1,
                          api_key=api_key,
                          api_secret=api_secret,
                          is_prod=True)

    while True:
        xrp_long.cycle()
