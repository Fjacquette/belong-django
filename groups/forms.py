from django import forms

from .models import Group


class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ["name", "description", "access"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}
        labels = {"access": "Group access"}
        help_texts = {"access": "Open: visible, join immediately. Closed: visible, request approval. Unlisted: join immediately through a link. Private: hidden, invitation only (invitations coming next)."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "mt-1 w-full min-w-0 border rounded-xl px-3 py-2 bg-white"
