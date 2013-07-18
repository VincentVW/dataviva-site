# -*- coding: utf-8 -*- 
import urllib2
import json
from datetime import datetime
from sqlalchemy import func
from flask import Blueprint, request, render_template, g, Response, make_response, send_file, jsonify, redirect, url_for

from visual import db
from visual.data.forms import DownloadForm
from visual.account.models import User, Starred
from visual.attrs.models import Bra, Wld
from visual.rais.models import Isic, Cbo
from visual.secex.models import Hs

from visual.utils import Pagination

import json

mod = Blueprint('data', __name__, url_prefix='/data')

@mod.before_request
def before_request():
    g.page_type = mod.name
    
    g.sabrina = {}
    g.sabrina["outfit"] = "lab"
    g.sabrina["face"] = "smirk"
    g.sabrina["hat"] = "glasses"

def get_geo_location(ip):
    req = urllib2.Request("http://freegeoip.net/json/" + ip)
    opener = urllib2.build_opener()
    try:
        f = opener.open(req)
    except:
        return None
    json_resp = json.loads(f.read())
    city = json_resp["city"]
    # city = "Viana"
    state = json_resp["region_name"]
    # state = "Espírito Santo"
    # state = "Maranhão"
    
    # first try to find the exact city within the state
    bra_state = Bra.query.filter_by(name_pt=state).filter(func.char_length(Bra.id) == 2).first()
    bra_cities = Bra.query.filter_by(name_pt=city).filter(func.char_length(Bra.id) == 8)
    if bra_state:
        if bra_cities.count() == 1:
            return bra_cities.first()
        elif bra_cities.count() > 1:
            return bra_cities.filter(Bra.id.like(bra_state.id+'%')).first()
        return None
    return None

@mod.route('/')
def index():
    return render_template("data/index.html")

@mod.route('/query/')
def query():
    g.page_type = "query"
    # try getting the user's ip address, since the live server is using a proxy
    # nginx, we need to use the "X-Forwarded-For" remote address otherwise
    # this will always be 127.0.0.1 ie localhost
    if not request.headers.getlist("X-Forwarded-For"):
        ip = request.remote_addr
    else:
        ip = request.headers.getlist("X-Forwarded-For")[0]
    
    # next try geolocating the user's ip
    geo_location = get_geo_location(ip) or None
    
    # if the city or region is not found in the db use Belo Horizonte as default
    if not geo_location:
        geo_location = Bra.query.get("mg030000")
    
    return render_template("data/query.html", geo_location = geo_location)

@mod.route('/classifications/')
@mod.route('/classifications/<attr>/')
@mod.route('/classifications/<attr>/<depth>/')
@mod.route('/classifications/<attr>/<depth>/<int:page>/')
def classifications(attr = None, depth = None, page = 1):
    
    if not attr:
        return render_template("data/select.html")
    
    g.page_type = "classifications"
    per_page = 50
    offset = request.args.get("offset", 0)
    
    if attr == "bra":
        attr_table = Bra
        if depth == None:
            depth = "2"
        depths = ["2","4","6","8"]
        title = "Brazilian Geography"
    elif attr == "wld":
        attr_table = Wld
        if depth == None:
            depth = "2"
        depths = ["2","5"]
        title = "Countries"
    elif attr == "isic":
        attr_table = Isic
        if depth == None:
            depth = "1"
        depths = ["1","3","5"]
        title = "Industries by ISIC Classification"
    elif attr == "cbo":
        attr_table = Cbo
        if depth == None:
            depth = "1"
        depths = ["1","4"]
        title = "Occupations by CBO Classification"
    elif attr == "hs":
        attr_table = Hs
        if depth == None:
            depth = "2"
        depths = ["2","4","6"]
        title = "Products by HS Classification"
    
    attrs = attr_table.query.filter(func.char_length(attr_table.id) == depth).limit(per_page).offset(offset)
    
    if request.is_xhr:
        attrs_json = [dict(a.serialize().items() + [("attr_type",attr)]) for a in attrs]
        return jsonify({"data": attrs_json})
    
    return render_template("data/classifications.html",
        title = title,
        page_attr = attr,
        depth = depth,
        depths = depths,
        attrs = attrs)

@mod.route('/download/', methods=['GET', 'POST'])
def download():
    import tempfile, subprocess
    
    form = DownloadForm()

    data = form.data.data
    format = form.output_format.data
    title = form.title.data

    temp = tempfile.NamedTemporaryFile()
    temp.write(data.encode("utf-8"))
    temp.seek(0)

    if format == "png":
        mimetype='image/png'
    elif format == "pdf":
        mimetype='application/pdf'
    elif format == "svg":
        mimetype='application/octet-stream'
    elif format == "csv":
        mimetype="text/csv;charset=UTF-8"

    if format == "png" or format == "pdf":
        zoom = "1"
        background = "#ffffff"
        p = subprocess.Popen(["rsvg-convert", "-z", zoom, "-f", format, "--background-color={0}".format(background), temp.name], stdout=subprocess.PIPE)
        out, err = p.communicate()  
        response_data = out
    else:
        response_data = data.encode("utf-8")
    
    content_disposition = "attachment;filename=%s.%s" % (title, format)
    content_disposition = content_disposition.replace(",", "_")

    return Response(response_data, 
                        mimetype=mimetype, 
                        headers={"Content-Disposition": content_disposition})