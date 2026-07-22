"""Pure state machine for the SmartCounter widget.

No hardware/display imports so it is host-testable. Rendering (odometer reels,
flanking confirm/cancel buttons) lives in the display layer and reads this state.

Interaction contract: every -/+ tap enters a *pending* state (the committed
value does not move); the preview shows the target. confirm() commits, cancel()
reverts. Automated changes use set() to bypass the pending flow.
"""


class CounterState:
    def __init__(self, value, minimum=0, maximum=99):
        self.value = value
        self.minimum = minimum
        self.maximum = maximum
        self.pending = False
        self._delta = 0

    def _clamp(self, v):
        return max(self.minimum, min(self.maximum, v))

    @property
    def delta(self):
        return self._delta

    @property
    def preview(self):
        """The target value if the pending delta were committed."""
        return self._clamp(self.value + self._delta)

    def tap(self, step):
        """Enter/continue pending mode, accumulating the delta."""
        self.pending = True
        self._delta += step

    def confirm(self):
        """Commit the pending preview as the new value."""
        self.value = self.preview
        self._delta = 0
        self.pending = False

    def cancel(self):
        """Discard the pending delta, keep the current value."""
        self._delta = 0
        self.pending = False

    def zero(self):
        """Enter pending mode with the preview at 0 (reset button)."""
        self.pending = True
        self._delta = -self.value

    def set(self, value):
        """Set the value directly (automated change), clearing any pending state."""
        self.value = self._clamp(value)
        self._delta = 0
        self.pending = False
