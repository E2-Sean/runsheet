from django import forms
class UploadCsvForm(forms.Form):
    file = forms.FileField(label="CSV file")