# Code that attempts to remove the second calling of the APIs

if visits_data or facility_visits_data:
    # Convert datetime objects to strings
    for visit in visits_list:
        visit['start_at'] = visit['start_at'].isoformat() if visit['start_at'] else None
        visit['end_at'] = visit['end_at'].isoformat() if visit['end_at'] else None

    for fvisit in fvisits_list:
        fvisit['start_at'] = fvisit['start_at'].isoformat() if fvisit['start_at'] else None
        fvisit['end_at'] = fvisit['end_at'].isoformat() if fvisit['end_at'] else None

    request.session['visits_data'] = visits_list
    request.session['facility_visits_data'] = fvisits_list
    request.session['parameters'] = {'employee': alayacare_employee_id, 'start_date_from': start_date_from, 'start_date_to': start_date_to}

# ... [rest of the code] ...
