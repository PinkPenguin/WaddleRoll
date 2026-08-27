"""
core/plugin_base.py

Every game module (Fallout 4, PoE, Grim Dawn, Last Epoch, Hero Siege, ...)
implements this contract. The launcher shell only ever talks to modules
through this interface -- it never needs to know anything game-specific.

To add a new game later: create modules/<game>/module.py with a class
that subclasses GameModule, and the launcher will pick it up automatically
(see core/discovery.py).
"""

from abc import ABC, abstractmethod


class GameModule(ABC):
    # Unique short id, e.g. "fallout4", "poe2". Used internally (config
    # filenames, history log entries) -- never shown to the user directly.
    id: str = "unset"

    # Human-readable name shown on the game picker screen.
    display_name: str = "Unset Game"

    # Optional short description shown under the name on the picker.
    description: str = ""

    # Background color for this module's page (including the back-button
    # bar above it). Lets each game module own its full visual identity,
    # not just the content inside its widget.
    background_color: str = "#111118"

    # Window size applied when this module's page opens. default_size is
    # what the window resizes to; min_size is the floor the user can't
    # shrink below. Each module sets these to whatever actually fits its
    # own layout.
    default_size: tuple[int, int] = (900, 650)
    min_size: tuple[int, int] = (700, 500)

    # Shown on the game picker card. accent_color is used as a colored
    # stripe/highlight so each game reads distinctly even before opening
    # it. icon is a single character or emoji shown next to the name --
    # keeps things simple without needing real image assets per game.
    accent_color: str = "#7c5cff"
    icon: str = "🎮"

    @abstractmethod
    def get_widget(self, parent=None):
        """
        Return this module's main screen as a QWidget, ready to be mounted
        into the launcher's QStackedWidget. The module owns everything
        about its own layout, styling, and behavior from here down --
        the shell just displays whatever widget is returned.
        """
        raise NotImplementedError
