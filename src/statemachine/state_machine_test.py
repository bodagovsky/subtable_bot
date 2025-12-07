import pytest

from state_machine import StateMachine, UserState, Event

@pytest.fixture
def state_machine():
    return StateMachine()

@pytest.mark.parametrize("init_state, event_name, expected_state", [
    (UserState.INIT, Event.COMMAND_EXECUTED, UserState.INIT),
    (UserState.INIT, Event.COMMAND_UNCLEAR, UserState.PENDING_COMMAND_CLARFIFICATION),
    (UserState.INIT, Event.PARAMETERS_UNCLEAR, UserState.PENDING_COMMAND_PARAMETERS),
    (UserState.INIT, Event.IGNORE_USER, UserState.IGNORED),
    (UserState.PENDING_COMMAND_CLARFIFICATION, Event.COMMAND_UNCLEAR, UserState.PENDING_COMMAND_CLARFIFICATION),
    (UserState.PENDING_COMMAND_CLARFIFICATION, Event.PARAMETERS_UNCLEAR, UserState.PENDING_COMMAND_PARAMETERS),
    (UserState.PENDING_COMMAND_CLARFIFICATION, Event.IGNORE_USER, UserState.IGNORED),
    (UserState.PENDING_COMMAND_CLARFIFICATION, Event.COMMAND_EXECUTED, UserState.INIT),
    (UserState.PENDING_COMMAND_PARAMETERS, Event.PARAMETERS_UNCLEAR, UserState.PENDING_COMMAND_PARAMETERS),
    (UserState.PENDING_COMMAND_PARAMETERS, Event.COMMAND_EXECUTED, UserState.INIT),
    (UserState.IGNORED, Event.STOP_IGNORING, UserState.INIT),
])
def test_perform_transition_valid(state_machine, init_state, event_name, expected_state):
    result = state_machine.perform_transition(init_state, event_name)
    assert result is not None, f"Transition result should not be None for {init_state} and {event_name}"
    assert result is expected_state, f"Expected result state to be {expected_state}, got {result}"

@pytest.mark.parametrize("init_state, event_name", [
    (UserState.INIT, "invalid_event"),
    (UserState.PENDING_COMMAND_CLARFIFICATION, "not_an_event"),
    (UserState.IGNORED, ""),
    (UserState.PENDING_COMMAND_PARAMETERS, None),
])
def test_perform_transition_invalid_event(state_machine, init_state, event_name):
    result = state_machine.perform_transition(init_state, event_name)
    assert result is None, f"Result should be None for invalid event_name '{event_name}'"

@pytest.mark.parametrize("bad_state", [
    None,
    "INIT",
    42,
])
def test_perform_transition_invalid_state(state_machine, bad_state):
    # Valid event, but invalid state
    result = state_machine.perform_transition(bad_state, Event.COMMAND_EXECUTED)
    # It should error and return None
    assert result is None


@pytest.mark.parametrize("init_state, event_name, expected_state", [
    (UserState.IGNORED, Event.COMMAND_EXECUTED, None),
    (UserState.IGNORED, Event.PARAMETERS_UNCLEAR, None),
    (UserState.IGNORED, Event.COMMAND_UNCLEAR, None),
    (UserState.PENDING_COMMAND_PARAMETERS, Event.COMMAND_UNCLEAR, None),
])
def test_transition_invalid(state_machine, init_state, event_name, expected_state):
    result = state_machine.perform_transition(init_state, event_name)
    assert result is None, f"Expected result state to be None, got {result}"