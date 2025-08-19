import certifi
print(certifi.where())


import requests

response = requests.get(
    "https://centacare.alayacare.com",
    verify=certifi.where()
)

print(response)