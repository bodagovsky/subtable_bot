
from typing import Optional
from collections import defaultdict
from enum import Enum

class Event(Enum):
    COMMAND_EXECUTED = "command_executed"
    COMMAND_UNCLEAR = "command_unclear"
    PARAMETERS_UNCLEAR = "parameters_unclear"
    IGNORE_USER = "ignore_user"
    STOP_IGNORING = "stop_ignoring"

class UserState(Enum):
    INIT = 0
    PENDING_COMMAND_CLARIFICATION = 1
    PENDING_PARAMETERS_CLARIFICATION = 2
    IGNORED = 3


class StateMachine:
    def __init__(self) -> None:
        transitions = []
        import os
        transitions_path = os.path.join(os.path.dirname(__file__), "transitions.json")
        with open(transitions_path) as transitions_file:
            import json
            transitions = json.loads(transitions_file.read())
        
        self.transition_map = defaultdict[str, list](list)
        for t in transitions:
            self.transition_map[Event(t["condition"])].append((UserState[t["from"]], UserState[t["to"]]))

    def perform_transition(self, init_state: UserState, event: Event) -> Optional[UserState]:
        try:
            for state_pair in self.transition_map[event]:
                if state_pair[0] is init_state:
                    return state_pair[1]
            return None
        except Exception as e:
            print("Exceptions: ", e)
            return None


state_machine = StateMachine()