import requests
import json
from django.conf import settings
from django.shortcuts import render
from datetime import datetime, timedelta
from django.http import HttpResponse
from django.db import connection
from weasyprint import HTML
from django.template.loader import render_to_string
from collections import Counter
from collections import Counter
import aiohttp
import asyncio
import functools
import ssl
import certifi
import csv

# Caching dictionaries
client_cache = {}
risk_cache = {}
service_cache = {}
visit_cache = {}
facility_visit_cache = {}

# functions

# use to convert UI dates to UTC for API calls
def utc_date(string_date):
    date_date = datetime.strptime(string_date, "%Y-%m-%d")
    date_date -= timedelta(days=1)
    string_date = date_date.strftime("%Y-%m-%d 14:00")
    return f"'{string_date}'"

# generic async api call
async def make_async_api_call(url):

    ssl_context = ssl.create_default_context(cafile=certifi.where())

    # dodgy fix for the SSL CA issue - turn SSL verification off
    # ssl_context = ssl.create_default_context(cafile="C:\Program Files\Python311\Lib\site-packages\certifi\Gcacert.pem")
    #ssl_context = ssl.create_default_context(cafile="C:\\Python311\\Lib\\site-packages\\certifi\\cacert.pem")
    #ssl_context.check_hostname = False
    #ssl_context.verify_mode = ssl.CERT_NONE
    # insert ssl=ssl_context,  after session.get(url, below

    async with aiohttp.ClientSession() as session:
        async with session.get(url, ssl=ssl_context, auth=aiohttp.BasicAuth(settings.API_USER, settings.API_PASS)) as response:
            if response.status == 200:
                return await response.json()
            else:
                print(f"API call to {url} failed with status code: {response.status}")
                print(await response.text())
                return None

# specific async api calls with caching
async def get_client_data(client_id):
    if client_id not in client_cache:
        url = f"{settings.BASE_URL_ALAYACARE}/ext/api/v2/patients/clients/{client_id}"
        client_cache[client_id] = await make_async_api_call(url)
    return client_cache[client_id]

async def get_risks_data(client_id):
    if client_id not in risk_cache:
        url = f"{settings.BASE_URL_ALAYACARE}/ext/api/v2/clinical/clients/{client_id}/risks"
        risk_cache[client_id] = await make_async_api_call(url)
    return risk_cache[client_id]

async def get_service_data(service_id):
    if service_id not in service_cache:
        url = f"{settings.BASE_URL_ALAYACARE}/ext/api/v2/scheduler/services/{service_id}"
        service_cache[service_id] = await make_async_api_call(url)
    return service_cache[service_id]

async def get_visit(visit_id):
    if visit_id not in visit_cache:
        url = f"{settings.BASE_URL_ALAYACARE}/ext/api/v2/scheduler/visits/{visit_id}"
        visit_cache[visit_id] = await make_async_api_call(url)
    return visit_cache[visit_id]

async def get_facility_visit(visit_id):
    if visit_id not in facility_visit_cache:
        url = f"{settings.BASE_URL_ALAYACARE}/ext/api/v2/scheduler/facility_visits/{visit_id}"
        facility_visit_cache[visit_id] = await make_async_api_call(url)
    return facility_visit_cache[visit_id]

async def get_visits(alayacare_employee_id, start_date_from, start_date_to):
    start_date_from = utc_date(start_date_from)
    start_date_to = utc_date(start_date_to)
    url = f"{settings.BASE_URL_ALAYACARE}/ext/api/v2/scheduler/visits?alayacare_employee_id={alayacare_employee_id}&start_date_from={start_date_from}&start_date_to={start_date_to}"
    return await make_async_api_call(url)

async def get_facility_visits(alayacare_employee_id, start_date_from, start_date_to):
    start_date_from = utc_date(start_date_from)
    start_date_to = utc_date(start_date_to)
    url = f"{settings.BASE_URL_ALAYACARE}/ext/api/v2/scheduler/facility_visits?alayacare_employee_id={alayacare_employee_id}&start_at={start_date_from}&end_at={start_date_to}"
    return await make_async_api_call(url)

async def get_employee(employee_id):
    url = f"{settings.BASE_URL_ALAYACARE}/ext/api/v2/employees/employees/{employee_id}"
    return await make_async_api_call(url)

async def get_active_employees(filter_string):
    url = f"{settings.BASE_URL_ALAYACARE}/ext/api/v2/employees/employees?status=active&filter={filter_string}&page=1&count=1000"
    return await make_async_api_call(url)

def merge_and_sort(list_a, list_b):
    combined_list = list_a + list_b
    combined_list_sorted = sorted(combined_list, key=lambda d: d['start_at'])
    return combined_list_sorted

# views
def index(request):
    print(request.META)
    print(request.META) 
    return render(request, 'index.html')

async def runsheet_async(request):
    visits_list = []
    fvisits_list = []
    context = {}

    if request.method == 'POST':
        alayacare_employee_id = request.POST.get('employee')
        start_date_from = request.POST.get('start_date')
        start_date_to = request.POST.get('end_date')

        employee_data = await get_employee(alayacare_employee_id)

        if employee_data:
            employee_firstname = employee_data['demographics']['first_name']
            employee_lastname = employee_data['demographics']['last_name']

        visits_data = await get_visits(alayacare_employee_id, start_date_from, start_date_to)

        if visits_data:
            tasks = []
            for visit in visits_data['items']:
                if not visit.get('cancelled'):
                    client_task = get_client_data(visit.get('alayacare_client_id'))
                    risks_task = get_risks_data(visit.get('alayacare_client_id'))
                    service_task = get_service_data(visit.get('alayacare_service_id'))
                    visit_task = get_visit(visit.get('alayacare_visit_id'))
                    tasks.append((visit, client_task, risks_task, service_task, visit_task))

            results = await asyncio.gather(*[task[1] for task in tasks] + [task[2] for task in tasks] + [task[3] for task in tasks] + [task[4] for task in tasks])

            for i, task in enumerate(tasks):
                visit, client_data, risks_data, service_data, visit_data = task[0], results[i], results[len(tasks) + i], results[2 * len(tasks) + i], results[3 * len(tasks) + i]

                visit_dict = {
                    "visit_type": "home_visit",
                    "visit_id": visit.get('alayacare_visit_id'),
                    "service_id": visit.get('alayacare_service_id'),
                    "service_code_id": visit.get('service_code_id'),
                    "start_at": datetime.fromisoformat(visit.get('start_at')),
                    "end_at": datetime.fromisoformat(visit.get('end_at')),
                    "status": visit.get('status'),
                    "salutation": client_data.get('demographics', {}).get('salutation', ''),
                    "first_name": client_data['demographics']['first_name'],
                    "last_name": client_data['demographics']['last_name'],
                    "address": client_data['demographics']['address'],
                    "address_suite": client_data.get('demographics', {}).get('address_suite', ''),
                    #"address_suite": client_data['demographics',{}.get('address_suite','')], # handle null value if not in API JSON
                    "address_suite": client_data.get('demographics', {}).get('address_suite', ''),
                    #"address_suite": client_data['demographics',{}.get('address_suite','')], # handle null value if not in API JSON
                    "city": client_data['demographics']['city'],
                    "state": client_data['demographics']['state'],
                    "service_instructions": visit_data['service_instructions'],
                    "service_code_name": service_data.get('service_code_name') if service_data else '',
                    "risks_data": risks_data['items'] if risks_data else []
                }

                visits_list.append(visit_dict)

        facility_visits_data = await get_facility_visits(alayacare_employee_id, start_date_from, start_date_to)

        if facility_visits_data:
            facility_tasks = []
            for fvisit in facility_visits_data['items']:
                if not fvisit.get('cancelled'):
                    facility_visit_task = get_facility_visit(fvisit.get('alayacare_visit_id'))
                    service_task = get_service_data(fvisit.get('alayacare_service_id'))
                    facility_tasks.append((fvisit, facility_visit_task, service_task))

            facility_results = await asyncio.gather(*[task[1] for task in facility_tasks] + [task[2] for task in facility_tasks])

            for i, task in enumerate(facility_tasks):
                fvisit, facility_visit_data, service_data = task[0], facility_results[i], facility_results[len(facility_tasks) + i]

                fvisit_dict = {
                    "visit_type": "facility_visit",
                    "visit_id": fvisit.get('alayacare_visit_id'),
                    "start_at": datetime.fromisoformat(fvisit.get('start_at')),
                    "end_at": datetime.fromisoformat(fvisit.get('end_at')),
                    "status": fvisit.get('status'),
                    "facility": facility_visit_data['facility']['full_name'],
                    "service_name": facility_visit_data['service']['name'],
                    "service_instructions": facility_visit_data['service_instructions'],
                    "service_code_name": service_data.get('service_code_name') if service_data else ''
                }

                fvisits_list.append(fvisit_dict)

        context['employee_details'] = {'employee_firstname': employee_firstname, 'employee_lastname': employee_lastname}
        context['parameters'] = {'employee': alayacare_employee_id, 'start_date_from': start_date_from, 'start_date_to': start_date_to}
        context['visits'] = merge_and_sort(visits_list, fvisits_list)

        return render(request, 'runsheet2.html', context)

    else:
        filter_string = 'AGENCY'
        employees_data = await get_active_employees(filter_string)

        if not employees_data:
            context = {'error': 'Failed to load employee data'}
            return render(request, 'runsheet.html', context)

        sorted_employees = sorted(employees_data['items'], key=lambda x: (x['first_name'], x['last_name']))
        context = {'employees': sorted_employees}
        return render(request, 'runsheet.html', context)

# Wrap the async view to work with Django
def runsheet(request):
    return asyncio.run(runsheet_async(request))

# version for staff runsheet
def runsheet_staff(request):
    return render(request, 'runsheet_staff.html')

def runsheet_staff_search(request):
    employee_list = []
    context = {}

    if request.method == 'GET':
        return render(request, 'runsheet_staff_search.html')

    if request.method == 'POST':
        filter_string = request.POST.get('employee')
        employees_data = asyncio.run(get_active_employees(filter_string))

        if employees_data:
            for employee in employees_data['items']:
                employee_dict = {
                    "id": employee.get('id'),
                    "first_name": employee.get('first_name'),
                    "last_name": employee.get('last_name')
                }
                employee_list.append(employee_dict)

        context['employees'] = employee_list
        return render(request, 'runsheet_staff_select.html', context)

# to do - attempt to avoid the repeated web service calls
async def generate_pdf_async(request):
    visits_list = []
    fvisits_list = []
    context = {}

    if request.method == 'POST':
        alayacare_employee_id = request.POST.get('employee')
        start_date_from = request.POST.get('start_date')
        start_date_to = request.POST.get('end_date')

        employee_data = await get_employee(alayacare_employee_id)

        if employee_data:
            employee_firstname = employee_data['demographics']['first_name']
            employee_lastname = employee_data['demographics']['last_name']

        visits_data = await get_visits(alayacare_employee_id, start_date_from, start_date_to)

        if visits_data:
            tasks = []
            for visit in visits_data['items']:
                if not visit.get('cancelled'):
                    client_task = get_client_data(visit.get('alayacare_client_id'))
                    risks_task = get_risks_data(visit.get('alayacare_client_id'))
                    service_task = get_service_data(visit.get('alayacare_service_id'))
                    visit_task = get_visit(visit.get('alayacare_visit_id'))
                    tasks.append((visit, client_task, risks_task, service_task, visit_task))

            results = await asyncio.gather(*[task[1] for task in tasks] + [task[2] for task in tasks] + [task[3] for task in tasks] + [task[4] for task in tasks])

            for i, task in enumerate(tasks):
                visit, client_data, risks_data, service_data, visit_data = task[0], results[i], results[len(tasks) + i], results[2 * len(tasks) + i], results[3 * len(tasks) + i]

                visit_dict = {
                    "visit_type": "home_visit",
                    "visit_id": visit.get('alayacare_visit_id'),
                    "service_id": visit.get('alayacare_service_id'),
                    "service_code_id": visit.get('service_code_id'),
                    "start_at": datetime.fromisoformat(visit.get('start_at')),
                    "end_at": datetime.fromisoformat(visit.get('end_at')),
                    "status": visit.get('status'),
                    "salutation": client_data.get('demographics', {}).get('salutation', ''), # handle null value if not in API JSON
                    "salutation": client_data.get('demographics', {}).get('salutation', ''), # handle null value if not in API JSON
                    "first_name": client_data['demographics']['first_name'],
                    "last_name": client_data['demographics']['last_name'],
                    "address": client_data['demographics']['address'],
                    "address_suite": client_data.get('demographics', {}).get('address_suite', ''),
                    #"address_suite": client_data['demographics',{}.get('address_suite','')], # handle null value if not in API JSON
                    "address_suite": client_data.get('demographics', {}).get('address_suite', ''),
                    #"address_suite": client_data['demographics',{}.get('address_suite','')], # handle null value if not in API JSON
                    "city": client_data['demographics']['city'],
                    "state": client_data['demographics']['state'],
                    "service_instructions": visit_data['service_instructions'],
                    "service_code_name": service_data.get('service_code_name') if service_data else '',
                    "risks_data": risks_data['items'] if risks_data else []
                }

                visits_list.append(visit_dict)

        facility_visits_data = await get_facility_visits(alayacare_employee_id, start_date_from, start_date_to)

        if facility_visits_data:
            facility_tasks = []
            for fvisit in facility_visits_data['items']:
                if not fvisit.get('cancelled'):
                    facility_visit_task = get_facility_visit(fvisit.get('alayacare_visit_id'))
                    service_task = get_service_data(fvisit.get('alayacare_service_id'))
                    facility_tasks.append((fvisit, facility_visit_task, service_task))

            facility_results = await asyncio.gather(*[task[1] for task in facility_tasks] + [task[2] for task in facility_tasks])

            for i, task in enumerate(facility_tasks):
                fvisit, facility_visit_data, service_data = task[0], facility_results[i], facility_results[len(facility_tasks) + i]

                fvisit_dict = {
                    "visit_type": "facility_visit",
                    "visit_id": fvisit.get('alayacare_visit_id'),
                    "start_at": datetime.fromisoformat(fvisit.get('start_at')),
                    "end_at": datetime.fromisoformat(fvisit.get('end_at')),
                    "status": fvisit.get('status'),
                    "facility": facility_visit_data['facility']['full_name'],
                    "service_name": facility_visit_data['service']['name'],
                    "service_instructions": facility_visit_data['service_instructions'],
                    "service_code_name": service_data.get('service_code_name') if service_data else ''
                }

                fvisits_list.append(fvisit_dict)

        context['employee_details'] = {'employee_firstname': employee_firstname, 'employee_lastname': employee_lastname}
        context['parameters'] = {'employee': alayacare_employee_id, 'start_date_from': start_date_from, 'start_date_to': start_date_to}
        context['visits'] = merge_and_sort(visits_list, fvisits_list)
        context['dev_phase'] = {'dev_phase': settings.DEV_PHASE}

        html_string = render_to_string('runsheet_pdf.html', context)
        html = HTML(string=html_string, base_url=settings.BASE_URL_WEASYPRINT)
        pdf = html.write_pdf()

        start_date_from = context['parameters']['start_date_from']
        employee_firstname = context['employee_details']['employee_firstname']
        employee_lastname = context['employee_details']['employee_lastname']
        filename = f"{employee_firstname}_{employee_lastname}_{start_date_from}.pdf".replace(" ", "_")

        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename={filename}'

        return response

    else:
        filter_string = 'AGENCY'
        employees_data = await get_active_employees(filter_string)

        if not employees_data:
            context = {'error': 'Failed to load employee data'}
            return render(request, 'runsheet.html', context)

        context = {'employees': employees_data['items']}
        return render(request, 'runsheet.html', context)

def generate_pdf(request):
    return asyncio.run(generate_pdf_async(request))



def facility_list(request):
    # empty list for employees
    facility_list = []
    # query
    query = """
        SELECT
            facility_id,
            profile:name::string as facility_name
        FROM SHARED_FACILITY
        where left(profile:name::string,2) not in ('ZD','ZZ','Z ','ZN')
        order by profile:name::string
    """

    # Open a database cursor and execute the query
    with connection.cursor() as cursor:
        cursor.execute(query)
        # Fetch all rows
        rows = cursor.fetchall()
        # Get column names from cursor description
        columns = [col[0] for col in cursor.description]

        # Convert rows to a list of dictionaries
        facility_list = [dict(zip(columns, row)) for row in rows]

        #print(facility_list)

        #date calcs
        today = datetime.now().strftime("%Y-%m-%d")
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    # Pass the employees data to the template
    return render(request, 'facility_list.html', {'facility_list': facility_list, 'today': today, 'tomorrow': tomorrow,})

def facility_visits(request):

    # facility_id = 4708
    # start_at = '2024-11-07 00:00:00'
    # end_at = '2024-11-08 00:00:00'
    facility_visits = []
    meal_visits = None
    facility_name = ''

    if request.method == 'POST':
        facility_id = request.POST.get('facility')
        start_at = request.POST.get('start_date')
        end_at = request.POST.get('end_date')
        format = request.POST.get('format')

        format = request.POST.get('format')


    #facility_visits = []

    #facility_name = ''

    facility_query = """
        select profile:name::string as facility_name
        from SHARED_FACILITY
        where facility_id = %s
    """

    with connection.cursor() as cursor:
        cursor.execute(facility_query, [facility_id])
        row = cursor.fetchone()
        if row:
            facility_name = row[0]  # Assign facility name

    if format in ["meals", "meals_csv"]:
        meals_query = """
            select 
                c.client_id,
                c.profile:first_name::string as first_name, 
                c.profile:last_name::string as last_name, 
                v.service_instructions,
                count(*) as meal_count
            from shared_visit v
            join shared_client c on v.client_id = c.client_id
            where v.facility_id = %s
            and v.start_at >= %s
            and v.start_at < %s
            group by c.client_id, c.profile:first_name::string, c.profile:last_name::string, v.service_instructions
            order by c.profile:first_name::string, c.profile:last_name::string asc;
        """
        with connection.cursor() as cursor:
            cursor.execute(meals_query, [facility_id, start_at, end_at])
            # Fetch all rows
            rows = cursor.fetchall()
            # Get column names from cursor description
            columns = [col[0] for col in cursor.description]
        
            # Convert rows to a list of dictionaries
            meal_visits = [dict(zip(columns, row)) for row in rows]

        # Return CSV if requested
        if format == "meals_csv":
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="meal_visits_{facility_name}.csv"'
            writer = csv.DictWriter(response, fieldnames=columns)
            writer.writeheader()
            for row in meal_visits:
                writer.writerow(row)
            return response
    #else:
    #    meal_visits = None
    
    visit_query = """ 
        select 
            c.client_id as client_id, 
            c.profile:first_name::string as first_name,
            c.profile:last_name::string as last_name, 
            c.profile:address::string as address,
            c.profile:city::string as suburb,
            c.profile:zip::string as postcode,
            c.profile:phone_main::string as phone_main,
            to_char(v.start_at, 'YYYY-MM-DD HH24:MI') as start_at, 
            to_char(v.end_at,'YYYY-MM-DD HH24:MI') as end_at,
            sc.properties:name::string as service_code,
            v.service_instructions as service_instructions
        from shared_visit v
        join shared_client c on v.client_id = c.client_id
        join shared_service_code sc on v.service_code_id = sc.service_code_id
        where facility_id = %s
        and start_at >= %s
        and start_at < %s
        order by start_at asc;
    """
    # Open a database cursor and execute the query
    with connection.cursor() as cursor:
        cursor.execute(visit_query, [facility_id, start_at, end_at])
        # Fetch all rows
        rows = cursor.fetchall()
        # Get column names from cursor description
        columns = [col[0] for col in cursor.description]
        
        # Convert rows to a list of dictionaries
        facility_visits = [dict(zip(columns, row)) for row in rows]

        # Return CSV if requested
    if format == "normal_csv":
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="facility_visits_{facility_name}.csv"'
        writer = csv.DictWriter(response, fieldnames=columns)
        writer.writeheader()
        for row in facility_visits:
            writer.writerow(row)
        return response

    # If no csv return then pass the data to the HTML template
    return render(request, 'facility_visits.html', {'facility_visits': facility_visits, 'meal_visits': meal_visits, 'facility_name': facility_name, 'format': format})