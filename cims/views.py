from django.shortcuts import render

# Create your views here.

# cims/views.py
import os
import time

from pathlib import Path
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from .forms import UploadCsvForm
from django.contrib import messages
from django.db import connection
from django.db import connections  # add this (keep 'connection' if you still use it elsewhere)
from django.http import HttpResponseBadRequest
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.contrib.messages import get_messages
from django.http import JsonResponse

# UPLOAD CSV

@require_http_methods(["GET", "POST"])
def upload_csv(request):

    # clear messages
    list(get_messages(request))

    # set context for form
    ctx = {"form": UploadCsvForm()}

    if request.method == "POST":
        form = UploadCsvForm(request.POST, request.FILES)
        if form.is_valid():
            f = form.cleaned_data["file"]

            # Save under MEDIA_ROOT/uploads/YYYYMMDD/
            date_folder = time.strftime("%Y%m%d")
            upload_dir = Path(settings.MEDIA_ROOT) / "uploads" / date_folder
            upload_dir.mkdir(parents=True, exist_ok=True)

            storage = FileSystemStorage(location=str(upload_dir))
            saved_name = storage.save(f.name, f)
            saved_path = upload_dir / saved_name

            # folder_for_proc = str(upload_dir)
            # if not folder_for_proc.endswith("\\"):
            #     folder_for_proc += "\\"

            folder_for_proc = str(upload_dir).rstrip("/\\") + "\\"
            filename_for_proc = saved_name.lstrip("/\\")

            # # Efficient line count: count '\n' bytes in chunks
            # line_count = 0
            # with open(saved_path, "rb", buffering=1024 * 1024) as fh:
            #     for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            #         line_count += chunk.count(b"\n")

            # If your CSVs may not end with a newline, uncomment to count the last line:
            # with open(saved_path, "rb") as fh2:
            #     if not fh2.read().endswith(b"\n"):
            #         line_count += 1

            # inside the block where you build ctx after saving the file

            # update form context
            ctx.update({
                "form": UploadCsvForm(),
                "uploaded_path": str(saved_path),
                "uploaded_folder": str(upload_dir),   # <-- add this
                "relative_path": os.path.relpath(saved_path, settings.MEDIA_ROOT),
                "media_url": settings.MEDIA_URL,
                #"line_count": line_count,
                "filename": saved_name,
            })

            return render(request, "cims/upload_form.html", ctx, status=201)
        else:
            ctx["form"] = form  # re-render with validation errors

    return render(request, "cims/upload_form.html", ctx)


# RUN IMPORT 

@require_POST
def run_import(request):
    folder = request.POST.get("folder")
    filename = request.POST.get("filename")
    if not folder or not filename:
        return HttpResponseBadRequest("Missing folder or filename")

    media_uploads = (Path(settings.MEDIA_ROOT) / "uploads").resolve()
    folder_path = Path(folder).resolve()
    if not str(folder_path).lower().startswith(str(media_uploads).lower()):
        return HttpResponseBadRequest("Invalid folder")
    
    folder_param = str(folder_path)
    if not folder_param.endswith("\\"):
        folder_param += "\\"
    
    file_param = filename.lstrip("/\\")

    # hard coded test
    # folder_param = r"C:\repo\runsheet\media\uploads\\"  # note the trailing backslash
    # file_param   = "APE.csv"

    # Debug prints (these will go to your runserver/daphne log)
    # print("=== run_import debug ===")
    # print("Folder param:", folder_param)
    # print("File param:", file_param)
    # print("========================")

    sql = """
        EXEC [sub].[sp_010_Load_Alayacare_Payroll_Export]
            @ac_payroll_export_folder=%s,
            @ac_payroll_export_file=%s
    """

    try:
        # Use the SQL Server connection explicitly:
        with connections['mssql'].cursor() as cursor:
            # 1) Run stored proc
            cursor.execute(sql, [folder_param, file_param])

            # 2) Read the current table row count
            cursor.execute("SELECT COUNT(*) FROM sub.alayacare_payroll_export;")
            (table_count,) = cursor.fetchone()
            
            #rows = cursor.rowcount  # may be -1 for some procs
        messages.success(
            request,
            f"Import complete for {file_param}. Current row count in sub.alayacare_payroll_export: {table_count:,}"
        )
        
    except Exception as ex:
        messages.error(request, f"Import failed: {ex}")
        return render(request, "cims/import_result.html")

    return render(request, "cims/import_result.html", {"row_count": table_count})

# DB PROBE

def db_probe(request):
    try:
        with connections['mssql'].cursor() as c:
            c.execute("SELECT @@VERSION")
            ver = c.fetchone()[0]
        return HttpResponse(f"OK: {ver}")
    except Exception as ex:
        return HttpResponse(f"ERROR: {ex}", status=500)

# REMOVE DUPLICATES

# Duplicate Query 

from django.views.decorators.http import require_http_methods
from django.db import connections
from django.contrib import messages
from django.shortcuts import render, redirect
from django.urls import reverse

DUP_QUERY = """
WITH duplicates AS (
    SELECT
        visit_id,
        payroll_number,
        startdate,
        starttime,
        enddate,
        endtime,
        pay_code,
        COUNT(*) AS duplicate_count
    FROM sub.alayacare_payroll_export
    WHERE pay_code NOT IN ('160','161')
    GROUP BY
        visit_id,
        payroll_number,
        startdate,
        starttime,
        enddate,
        endtime,
        pay_code
    HAVING COUNT(*) > 1
)
SELECT
    e.record_id,
    e.visit_id,
    e.payroll_number AS employee_no,
    e.pay_code,
    e.startdate,
    LEFT(e.starttime, 5) AS starttime,  -- if time is stored as string; use FORMAT(e.starttime,'HH:mm') if it's time/datetime
    e.enddate,
    LEFT(e.endtime, 5) AS endtime,
    ROW_NUMBER() OVER (
        PARTITION BY e.visit_id, e.payroll_number, e.startdate, e.starttime, e.enddate, e.endtime, e.pay_code
        ORDER BY e.record_id
    ) AS row_num,
    d.duplicate_count,
    e.audit_note
FROM sub.alayacare_payroll_export e
JOIN duplicates d
  ON e.visit_id       = d.visit_id
 AND e.payroll_number = d.payroll_number
 AND e.startdate      = d.startdate
 AND e.starttime      = d.starttime
 AND e.enddate        = d.enddate
 AND e.endtime        = d.endtime
 AND e.pay_code       = d.pay_code
ORDER BY e.visit_id, e.startdate, e.starttime;
"""

@require_http_methods(["GET", "POST"])
def remove_duplicates(request):
    if request.method == "POST":
        selected = request.POST.getlist("record_ids")
        ids = [int(x) for x in selected if x.isdigit()]
        if not ids:
            messages.warning(request, "No rows selected.")
            return redirect(reverse("cims:remove_duplicates"))

        placeholders = ",".join(["%s"] * len(ids))

        # 1) Insert to audit with audit_note='Duplicate'
        insert_sql = f"""
        INSERT INTO sub.alayacare_payroll_audit
        (
            record_id, visit_id, payroll_number, pay_code,
            startdate, starttime, enddate, endtime, audit_note
        )
        SELECT
            e.record_id, e.visit_id, e.payroll_number, e.pay_code,
            e.startdate, e.starttime, e.enddate, e.endtime,
            CAST('Duplicate' AS nvarchar(255)) AS audit_note
        FROM sub.alayacare_payroll_export e
        WHERE e.record_id IN ({placeholders});
        """

        # 2) Delete from export
        delete_sql = f"""
        DELETE FROM sub.alayacare_payroll_export
        WHERE record_id IN ({placeholders});
        """

        # Execute in one connection (single transaction depending on autocommit settings)
        deleted_count = 0
        try:
            with connections['mssql'].cursor() as c:
                c.execute(insert_sql, ids)
                c.execute(delete_sql, ids)
                # rowcount is reliable for a simple DELETE
                deleted_count = max(c.rowcount or 0, 0)
        except Exception as ex:
            return render(request, "cims/duplicates_deleted.html", {
                "deleted_count": 0,
                "error": str(ex),
            }, status=500)

        # 3) Show results page with a button to next step
        return render(request, "cims/duplicates_deleted.html", {
            "deleted_count": deleted_count,
            "error": None,
        })


    # GET → show duplicates
    with connections['mssql'].cursor() as c:
        c.execute(DUP_QUERY)
        cols = [col[0] for col in c.description]
        rows = [dict(zip(cols, r)) for r in c.fetchall()]

    # Count groups & rows for the header
    dup_groups = {}
    for r in rows:
        key = (r["visit_id"], r["employee_no"], r["startdate"], r["starttime"], r["enddate"], r["endtime"], r["pay_code"])
        dup_groups[key] = dup_groups.get(key, 0) + 1

    return render(request, "cims/remove_duplicates.html", {
        "rows": rows,
        "group_count": len(dup_groups),
        "row_count": len(rows),
    })

# REMOVE OVERLAPS

def remove_overlaps(request):
    return HttpResponse("Remove Overlaps – coming soon.")


# WHOAMI

def whoami(request):
    return JsonResponse({
        "user": str(request.user),
        "is_authenticated": request.user.is_authenticated,
        "META": {k: v for k, v in request.META.items() if "REMOTE" in k or "HTTP" in k},
    })