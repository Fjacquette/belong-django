from django import forms

from .models import Group


class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ["name", "description", "visibility", "join_policy"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}
        labels = {"visibility": "Who can see this group?", "join_policy": "How do people join?"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "mt-1 w-full min-w-0 border rounded-xl px-3 py-2 bg-white"
