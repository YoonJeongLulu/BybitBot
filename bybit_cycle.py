import json
import logging
import bybit_rest
import asyncio
import websockets
import time


class BybitCycle:
    def __init__(self, symbol, position, contracts, api_key, api_secret, is_prod):
        self.logger = None
        self.symbol = symbol
        self.api_key = api_key
        self.api_secret = api_secret
        self.market_price = 0
        self.position = position
        self.contracts = contracts
        self.is_prod = is_prod
        self.last_order_id = None
        self.last_order_link_id = None

    def set_logger(self):
        # Remove all handlers associated with the root logger object.
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

        logging.basicConfig(filename="logs/BybitCycle_" + str(time.time()) + ".log", format='%(asctime)s %(message)s')
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.INFO)
        self.logger.info("----------------")
        self.logger.info(f"Starting Bybit exchange {self.symbol} {self.position} Cycle")

    def cycle(self):
        print(f"새로운 {self.symbol}의 Cycle을 시작합니다.")

        # 포지션 오픈
        if self.open_position() and self.check_is_ordered():
            open_start_time = time.time()
            while True:
                if self.check_is_positioned("open"):
                    print("포지션이 잡혀있으니, 1분동안 홀딩하겠습니다..")
                    time.sleep(5)

                    # 포지션 청산
                    print("포지션 청산을 시도합니다..")
                    while True:
                        if self.close_position() and self.check_is_ordered():
                            close_start_time = time.time()
                            while True:
                                if self.check_is_positioned("close"):
                                    print("포지션 청산이 완료됐습니다..")
                                    return
                                else:
                                    time.sleep(10)

                                    if time.time() - close_start_time >= 120:
                                        print("지정가 포지션 청산이 이루어지지 않아 취소 후 재시도합니다..")
                                        if self.cancel_order():
                                            break
                                        close_start_time = time.time()
                else:
                    time.sleep(10)

                    if time.time() - open_start_time >= 120:
                        print("지정가 포지션 오픈이 이루어지지 않아 취소 후 재시도합니다..")
                        if self.cancel_order():
                            return
                        open_start_time = time.time()

    def get_market_price(self):
        my_loop = asyncio.get_event_loop()
        my_loop.run_until_complete(self.webSocket_bybit())
        self.logger.info(f"[BYBIT {self.symbol} {self.position} CYCLE] get_market_price: returned {self.market_price}")
        # my_loop.close();

    def get_wss_url(self):
        if self.is_prod:
            return "wss://stream.bybit.com/realtime"
        else:
            return "wss://stream-testnet.bybit.com/realtime"

    async def webSocket_bybit(self):
        async with websockets.connect(self.get_wss_url()) as websocket:
            print("Connected to bybit WebSocket")
            await websocket.send('{"op":"subscribe","args":["trade.' + self.symbol + '"]}')
            data_rcv_response = await websocket.recv()
            print("response for subscribe req. : " + data_rcv_response)

            data_rcv_strjason = await websocket.recv()
            data_rcv_dict = json.loads(data_rcv_strjason)
            data_trade_list = data_rcv_dict.get('data', 0)

            for data_trade_dict in data_trade_list:
                print("timestamp : " + data_trade_dict.get('timestamp', 0)
                      + ", price : " + str(data_trade_dict.get('price', 0))
                      + ", size : " + str(data_trade_dict.get('size', 0))
                      )
                self.market_price = float(data_trade_dict.get('price', 0))
                print()
                return

    def place_order(self, side):
        order_price = 0
        if (self.position == "long" and side == "Buy") or (self.position == "short" and side == "Sell"):
            order_price = self.market_price - 0.5
        elif (self.position == "long" and side == "Sell") or (self.position == "short" and side == "Buy"):
            order_price = self.market_price + 0.5

        kwargs = {"side": side,
                  "symbol": self.symbol,
                  "order_type": "Limit",
                  "qty": self.contracts,
                  "price": order_price,
                  "time_in_force": "PostOnly",
                  "api_key": self.api_key,
                  "timestamp": round(time.time() * 1000),
                  }

        param_str = bybit_rest.link_params(kwargs)
        sign_real = bybit_rest.generate_signiture(param_str, self.api_secret)

        method = "POST"
        url = bybit_rest.get_api_url(self.is_prod) + "bybit.com/v2/private/order/create"

        response = bybit_rest.send_req(url, method, kwargs, param_str, sign_real)

        if response.get('ret_msg') == 'OK':
            self.logger.info(
                f"[BYBIT {self.symbol} {self.position} CYCLE] place_order: returned {response.get('result')}")
            return response.get('result')
        else:
            self.logger.error(f"[BYBIT {self.symbol} {self.position} CYCLE] place_order: bad request")

    def cancel_order(self):
        kwargs = {
            "symbol": self.symbol,
            "order_id" : self.last_order_id,
            "order_link_id" : self.last_order_link_id,
            "api_key": self.api_key,
            "timestamp": round(time.time() * 1000),
        }

        param_str = bybit_rest.link_params(kwargs)
        sign_real = bybit_rest.generate_signiture(param_str, self.api_secret)

        method = "POST"
        url = bybit_rest.get_api_url(self.is_prod) + "bybit.com/v2/private/order/cancel"

        response = bybit_rest.send_req(url, method, kwargs, param_str, sign_real)

        if response.get('ret_msg') == 'OK':
            print(f"다음의 order_id {self.last_order_id} 주문이 취소되었습니다..")
            self.logger.info(
                f"[BYBIT {self.symbol} {self.position} CYCLE] cancel_order: returned {response.get('result')}")
            return response.get('result')
        else:
            print(f"다음의 order_id {self.last_order_id} 주문이 취소되지 않았습니다..")
            self.logger.error(f"[BYBIT {self.symbol} {self.position} CYCLE] cancel_order: bad request")

    def get_my_position(self):

        response = bybit_rest.get_position_list(self.api_key, self.api_secret, self.is_prod, self.symbol)

        if response.get('ret_msg') == 'OK':
            self.logger.info(
                f"[BYBIT {self.symbol} {self.position} CYCLE] get_my_position: returned {response.get('result')}")
            return response.get('result')
        else:
            self.logger.error(f"[BYBIT {self.symbol} {self.position} CYCLE] get_my_position: Bad Request")

    def get_active_order(self):
        kwargs = {
            "symbol": self.symbol,
            "api_key": self.api_key,
            "timestamp": round(time.time() * 1000),
        }

        param_str = bybit_rest.link_params(kwargs)
        sign_real = bybit_rest.generate_signiture(param_str, self.api_secret)

        method = "GET"
        url = bybit_rest.get_api_url(self.is_prod) + "bybit.com/v2/private/order"

        response = bybit_rest.send_req(url, method, kwargs, param_str, sign_real)

        if response.get('ret_msg') == 'OK':
            self.logger.info(
                f"[BYBIT {self.symbol} {self.position} CYCLE] get_active_order: returned {response.get('result')}")
            return response.get('result')
        else:
            self.logger.error(f"[BYBIT {self.symbol} {self.position} CYCLE] get_active_order: Bad Request")

    def check_is_ordered(self):
        print("주문이 들어갔는 지 확인합니다.")
        response = self.get_active_order()
        if response:
            print("현재 들어간 주문입니다.")
            self.logger.info(f"[BYBIT {self.symbol} {self.position} CYCLE] check_is_ordered: returned {response}")
            self.last_order_id = response[0]['order_id']
            self.last_order_link_id = response[0]['order_link_id']
            print("현재의 order_id", response[0]['order_id'])
            print()
            return True
        else:
            self.logger.info(f"[BYBIT {self.symbol} {self.position} CYCLE] check_is_ordered : Bad Request")
            return False

    def check_is_positioned(self, state):
        print("포지션이 잡혀있는 지 확인합니다..")
        response = self.get_my_position()

        if state == "open" and response['size'] != 0:
            print("다음과 같은 포지션이 잡혀있는 것을 확인했습니다..")
            self.logger.info(
                f"[BYBIT {self.symbol} {self.position} CYCLE] check_is_positioned: returned 'Current Position is {response.get('result')}'")
            print(response.get('result'))
            return True
        if state == "close" and response['size'] == 0:
            print("Close position을 하는 시점에 갖고 있는 포지션이 없습니다.")
            self.logger.info(
                f"[BYBIT {self.symbol} {self.position} CYCLE] check_is_positioned: returned 'No Position Now'")
            return True

    def open_position(self):
        print("포지션을 잡기 위한 시장가를 가져오고 있습니다..")
        self.get_market_price()

        if self.position == "long":
            side = "Buy"
        else:
            side = "Sell"

        response = self.place_order(side=side)
        if response is None:
            self.logger.info(
                f"[BYBIT {self.symbol} {self.position} CYCLE] open_position: returned 'Fail to open Position'")
            return False
        else:
            self.logger.info(
                f"[BYBIT {self.symbol} {self.position} CYCLE] open_position: returned {response.get('result')}")
            return True

    def close_position(self):
        self.get_market_price()

        if self.position == "long":
            side = "Sell"
        else:
            side = "Buy"

        # 청산 주문
        response = self.place_order(side=side)
        if response is None:
            self.logger.info(
                f"[BYBIT {self.symbol} {self.position} CYCLE] close_position: returned 'Fail to close Position'")
            print("포지션 청산 주문에 실패했습니다...")
            return False
        else:
            print("해당 포지션을 청산합니다.")
            print(response)
            return True

    def switch_to_isolated(self):
        kwargs = {
            "symbol": self.symbol,
            "is_isolated": True,
            "buy_leverage": 1,
            "sell_leverage": 1,
            "api_key": self.api_key,
            "timestamp": round(time.time() * 1000),
        }

        param_str = bybit_rest.link_params(kwargs)
        sign_real = bybit_rest.generate_signiture(param_str, self.api_secret)

        method = "POST"
        url = bybit_rest.get_api_url(self.is_prod) + "bybit.com/v2/private/position/switch-isolated"

        response = bybit_rest.send_req(url, method, kwargs, param_str, sign_real)

        if response.get('ret_msg') == 'OK':
            self.logger.info(
                f"[BYBIT {self.symbol} {self.position} CYCLE] switch_to_isolated: returned {response.get('result')}")
            print(f"switch_to_isolated: returned {response.get('result')}")
            return response.get('result')
        else:
            self.logger.error(f"[BYBIT {self.symbol} {self.position} CYCLE] switch_to_isolated: Bad Request")
