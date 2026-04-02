from django import forms

class UploadFileForm(forms.Form):
    file = forms.FileField(
        label='Fichier',
        widget=forms.FileInput(attrs={
            'accept': '.csv,.xlsx,.xls,.txt',
            'class': 'block w-full text-sm text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-blue-600 file:text-white hover:file:bg-blue-700',
        })
    )


class FilterRuleForm(forms.Form):
    field = forms.CharField(max_length=100)
    operator = forms.ChoiceField(choices=[
        ('equals', 'Égal à'),
        ('not_equals', 'Différent de'),
        ('contains', 'Contient'),
        ('not_contains', 'Ne contient pas'),
        ('startswith', 'Commence par'),
        ('endswith', 'Finit par'),
        ('in_list', 'Dans la liste (séparés par virgule)'),
        ('is_empty', 'Est vide'),
        ('not_empty', 'N\'est pas vide'),
    ])
    value = forms.CharField(required=False, max_length=500)


class FilterConfigForm(forms.Form):
    logic = forms.ChoiceField(
        choices=[('AND', 'ET (toutes)'), ('OR', 'OU (au moins une)')],
        initial='AND'
    )
    rules = forms.JSONField(required=False, widget=forms.HiddenInput())
