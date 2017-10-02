import logging
import random
from deploy.utils import (
    passphrase,
    amount_format,
    check_succesful_tx
)
import gevent

log = logging.getLogger(__name__)


class Bidder:
    approx_bid_txn_cost = 40000

    def __init__(self, web3, auction_contract, address):
        self.web3 = web3
        self.address = address
        self.auction_contract = auction_contract
        self.bid_interval_seconds = 5
        self.max_bid_ceiling = 0.6
        self.max_bid_price = 1000000
        self.min_bid_price = 1000
        self.last_missing_funds = 1e100

    def bid(self):
        missing_funds = self.auction_contract.call().missingFundsToEndAuction()
        if missing_funds == 0:
            return
        assert missing_funds <= self.last_missing_funds
        self.last_missing_funds = missing_funds
        balance = self.web3.eth.getBalance(self.address)
        max_bid = int(missing_funds * self.max_bid_ceiling)
        amount = int(max(0, min(balance - self.approx_bid_txn_cost, max_bid)))
        amount = min(amount, self.max_bid_price)
        amount = int(amount * random.random())
        if amount < self.min_bid_price:
            amount = missing_funds
        if amount == 0:
            amount = 1
        unlocked = self.web3.personal.unlockAccount(self.address, passphrase)
        assert unlocked is True
        log.info('BID bidder=%s, missing_funds=%.2e, balance=%d, amount=%s' %
                 (self.address, missing_funds, balance, amount_format(self.web3, amount)))
        txhash = self.auction_contract.transact({'from': self.address, "value": amount}).bid()
        receipt = check_succesful_tx(self.web3, txhash)
        assert receipt is not None

    def run(self):
        log.info('bidder=%s started' % (self.address))
        balance = self.web3.eth.getBalance(self.address)
        while balance > 0:
            self.bid()
            missing_funds = self.auction_contract.call().missingFundsToEndAuction()
            if missing_funds == 0:
                return
            balance = self.web3.eth.getBalance(self.address)
            gevent.sleep(random.random() * self.bid_interval_seconds)
        log.info('auction ended for {bidder}: not enough minerals'.format(bidder=self.address))
