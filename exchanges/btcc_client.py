# exchanges/btcc_client.py

import hashlib
import logging
from typing import Any, Dict, Optional

import requests
from urllib.parse import quote

log = logging.getLogger(__name__)


class BTCCClient:
    """
    Thin wrapper over BTCC Trade OpenAPI (04/25/2025).
    Handles:
      - /v1/user/login
      - /v1/account/account
      - /v1/account/positionlist
      - /v1/account/openposition
      - /v1/account/closeposition
    """

    def __init__(
        self,
        base_url: str,
        user_name: str,
        password: str,
        api_key: str,
        secret_key: str,
        company_id: int = 1,
        timeout: int = 10,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.user_name = user_name
        self.password = password
        self.api_key = api_key
        self.secret_key = secret_key
        self.company_id = company_id
        self.timeout = timeout

        self.token: Optional[str] = None
        self.account_id: Optional[int] = None

    # ---------- signing ----------

    def _build_signed_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Implements the signature process from the BTCC doc:

        1. Add api_key and secret_key.
        2. Sort parameter names in ASCII order.
        3. URL-encode keys/values, build "k=v&..." string.
        4. MD5 of that string -> sign.
        5. Add `sign` to final params.

        NOTE: Doc examples include `secret_key` in the query itself, so we keep it.
        If BTCC later says not to send it, you would simply remove it before return.
        """
        p: Dict[str, Any] = dict(params)
        p["api_key"] = self.api_key
        p["secret_key"] = self.secret_key

        # build string for signature
        items = sorted(p.items(), key=lambda kv: kv[0])
        query = "&".join(
            f"{quote(str(k), safe='')}={quote(str(v), safe='')}" for k, v in items
        )
        sign = hashlib.md5(query.encode("utf-8")).hexdigest()

        p["sign"] = sign
        return p

    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = self.base_url + path
        signed = self._build_signed_params(params)
        resp = requests.get(url, params=signed, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"BTCC GET {path} error: {data}")
        return data

    def _post(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = self.base_url + path
        signed = self._build_signed_params(params)
        # API is form-encoded; using data= (not json=)
        resp = requests.post(url, data=signed, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"BTCC POST {path} error: {data}")
        return data

    # ---------- public methods ----------

    def login(self) -> None:
        """
        POST /v1/user/login

        Params (from PDF):
          - user_name: email or mobile
          - password
          - company_id: default 1
          - api_key
          - sign
        """
        params = {
            "user_name": self.user_name,
            "password": self.password,
            "company_id": self.company_id,
        }
        data = self._post("/v1/user/login", params)

        self.token = data["token"]
        acct = data["account"]
        self.account_id = int(acct["id"])
        log.info(
            "BTCC login ok | account_id=%s account_no=%s",
            self.account_id,
            acct.get("account_no"),
        )

    def ensure_logged_in(self) -> None:
        if not self.token or not self.account_id:
            self.login()

    def get_account_info(self) -> Dict[str, Any]:
        """
        GET /v1/account/account
        Params:
          - token
          - accountid
          - api_key, sign (via _build_signed_params)
        """
        self.ensure_logged_in()
        data = self._get(
            "/v1/account/account",
            {
                "token": self.token,
                "accountid": self.account_id,
            },
        )
        return data["account"]

    def get_positions(self, page: int = 1, page_size: int = 50) -> Dict[str, Any]:
        """
        GET /v1/account/positionlist
        Key params from doc:
          - token
          - accountid
          - page_index
          - page_size
        """
        self.ensure_logged_in()
        data = self._get(
            "/v1/account/positionlist",
            {
                "token": self.token,
                "accountid": self.account_id,
                "page_index": page,
                "page_size": page_size,
            },
        )
        return data

    def open_position(
        self,
        symbol: str,
        direction: int,
        volume: float,
        price: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        multiple: int = 20,
        ref_id: int | None = None,
        ref_accid: int | None = None,
    ) -> Dict[str, Any]:
        """
        POST /v1/account/openposition

        Doc param names (page 8):
          - token (string, Yes)
          - accountid (uint64, Yes)
          - direction (uint32, Yes) 1=Buy, 2=Sell
          - symbol (string, Yes)
          - request_volume (double, Yes)
          - request_price (double, Yes)
          - refid (uint64, No)
          - ref_accid (uint64, No)
          - stop_loss (double, No)
          - take_profit (double, No)
          - multiple (uint16, Yes)  leverage
          - sign (string, Yes)

        For a pure market order, some venues accept request_price=0.
        Check BTCC docs; otherwise you can pass best bid/ask.
        """
        self.ensure_logged_in()

        params: Dict[str, Any] = {
            "token": self.token,
            "accountid": self.account_id,
            "direction": direction,
            "symbol": symbol,
            "request_volume": volume,
            "request_price": price,
            "multiple": multiple,
        }

        if stop_loss is not None:
            params["stop_loss"] = stop_loss
        if take_profit is not None:
            params["take_profit"] = take_profit
        if ref_id is not None:
            params["refid"] = ref_id
        if ref_accid is not None:
            params["ref_accid"] = ref_accid

        data = self._post("/v1/account/openposition", params)
        return data["position"]

    def close_position(
        self,
        position_id: int,
        volume: float,
        price: float,
        ref_id: int | None = None,
    ) -> Dict[str, Any]:
        """
        POST /v1/account/closeposition

        Doc param names (page 10/around 14617):
          - token
          - accountid
          - positionid
          - request_volume
          - request_price
          - refid (optional)
          - sign
        """
        self.ensure_logged_in()

        params: Dict[str, Any] = {
            "token": self.token,
            "accountid": self.account_id,
            "positionid": position_id,
            "request_volume": volume,
            "request_price": price,
        }
        if ref_id is not None:
            params["refid"] = ref_id

        data = self._post("/v1/account/closeposition", params)
        return data["position"]
