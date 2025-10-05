from django.contrib.auth.forms import AuthenticationForm, UserCreationForm


BASE_INPUT_CLASSES = (
    "w-full rounded-xl border border-slate-200/70 px-4 py-3 text-base "
    "focus:border-rocket-magenta focus:ring-2 focus:ring-rocket-magenta/40 transition"
)


class StyledAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{css} {BASE_INPUT_CLASSES}".strip()
            if name == "username":
                field.widget.attrs.setdefault("placeholder", "Username")
            if name == "password":
                field.widget.attrs.setdefault("placeholder", "Password")


class StyledUserCreationForm(UserCreationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{css} {BASE_INPUT_CLASSES}".strip()
            placeholders = {
                "username": "Choose a username",
                "password1": "Create a password",
                "password2": "Confirm password",
            }
            if name in placeholders:
                field.widget.attrs.setdefault("placeholder", placeholders[name])
            field.help_text = None
