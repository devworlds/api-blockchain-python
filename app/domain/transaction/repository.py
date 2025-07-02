from abc import ABC, abstractmethod


class TransactionRepository(ABC):
    @abstractmethod
    def is_token_transaction(self, transaction_hash: str) -> bool:
        pass

    @abstractmethod
    def get_transaction(self, transaction_hash: str) -> dict:
        pass

    @abstractmethod
    def is_valid_transaction(self, transaction_hash: str) -> bool:
        pass
