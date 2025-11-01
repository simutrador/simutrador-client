
````mermaid
sequenceDiagram
autonumber
actor APP as demo/demo_sdk_usage.py
participant WS as src/simutrador_client/websocket.py
participant SRV as server:/ws/simulate

APP->>WS: async with WS: connect()
WS->>SRV: Open WebSocket (compose_ws_url -> /ws/simulate)
WS->>WS: Start _recv_loop()

APP->>WS: start_simulation(...)
WS->>SRV: send {type:start_simulation, request_id}
SRV-->>WS: {type:session_created, request_id, data.session_id}
WS->>WS: _dispatch -> resolve request future
WS-->>APP: return session_id

APP->>WS: wait_for_history_snapshot(session_id)
SRV-->>WS: {type:history_snapshot, data.session_id}
WS->>WS: _dispatch -> pending[session].history.set_result
WS-->>APP: return history snapshot

APP->>WS: subscribe_ticks / subscribe_fills / subscribe_account
WS-->>APP: return asyncio.Queue per subscription

par Streaming
  SRV-->>WS: {type:tick}           ; WS->>APP: enqueue -> ticks_q.get()
and
  SRV-->>WS: {type:execution_report}; WS->>APP: enqueue -> fills_q.get()
and
  SRV-->>WS: {type:account_snapshot}; WS->>APP: enqueue -> account_q.get()
end

APP->>WS: wait_for_simulation_end(session_id)
SRV-->>WS: {type:simulation_end}
WS->>WS: _dispatch -> pending[session].ended.set_result
WS-->>APP: return simulation_end

alt session_error path
  SRV-->>WS: {type:session_error, error_code, message}
  WS-->>APP: raise SessionError (pending waiter/request)
end

APP->>WS: close()
WS->>SRV: Close WebSocket
````
