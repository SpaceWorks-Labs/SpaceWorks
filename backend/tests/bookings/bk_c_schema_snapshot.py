"""BK-C's literal schema adapter for this Django-free host; compare live at integration."""
import json
from copy import deepcopy
from pathlib import Path

PATH = Path('frontend/openapi-schema.json')
schema = json.loads(PATH.read_text(encoding='utf-8'))
components = schema['components']['schemas']
paths = schema['paths']
string = {'type':'string'}
date = {'type':'string','format':'date-time'}
nullable_date = {**date,'nullable':True}
status = {'type':'string','enum':['pending','confirmed','rejected','cancelled','completed','no_show']}
def component(props): return {'type':'object','properties':props,'required':sorted(props)}
components['BookingConfirmation'] = component({
 'public_token': {'type':'string','format':'uuid'}, 'space_name':string,'timezone':string,
 'starts_at':date,'ends_at':date,'status':status,'location':string,'description':string,
 'arrived_at':nullable_date,'can_cancel':{'type':'boolean'},'cancellation_cutoff_at':date,
 'qr_value':{'type':'string','nullable':True},'google_calendar_url':{'type':'string','format':'uri'},
})
components['BookingArrival'] = component({
 'booking_id':{'type':'integer'},'display_name':string,'space_name':string,'timezone':string,
 'starts_at':date,'ends_at':date,'status':status,'arrived_at':nullable_date,
 'can_arrive':{'type':'boolean'},'can_reverse':{'type':'boolean'},
 'waiver_state':{'type':'string','enum':['not_required','current','missing']},
})
components['BookingCredential'] = component({'credential':{'type':'string','writeOnly':True,'maxLength':128}})
components['BookingCredential']['additionalProperties'] = False
components['PublicBookingResponse']['properties'].update({'public_token':{'type':'string','format':'uuid','readOnly':True},'confirmation_available':{'type':'boolean','readOnly':True},'amount_due':{'type':'string','nullable':True,'readOnly':True},'currency':{'type':'string','nullable':True,'readOnly':True},'pay_online':{'type':'boolean','readOnly':True}})
components['PublicBookingResponse']['properties'].pop('confirmation_url',None)
components['PublicBookingResponse']['required'] = ['status','confirmation_available','amount_due','currency','pay_online']
import runpy
response_schema = runpy.run_path("backend/apps/bookings/serializers_confirmation_result.py")["BOOKING_SUBMISSION_RESPONSE"]
components.pop('PublicBookingHoneypotResponse',None)
components.pop('PublicBookingSubmissionResponse',None)
paths['/api/v1/public/{makerspace_slug}/spaces/{public_token}/book/']['post']['responses']['201']['content']['application/json']['schema'] = response_schema
components['MemberBooking']['properties']['confirmation_available'] = {'type':'boolean','readOnly':True}
components['MemberBooking']['required'] = sorted(set(components['MemberBooking']['required']) | {'confirmation_available'})
components['BookableSpaceAdmin']['properties']['checkin_enabled'] = {'type':'boolean','readOnly':True}
components['BookableSpaceAdmin']['required'] = sorted(set(components['BookableSpaceAdmin']['required']) | {'checkin_enabled'})
security = deepcopy(paths['/api/v1/public/{makerspace_slug}/my-bookings/']['get']['security'])
errors = {str(code):{'description':desc,'content':{'application/json':{'schema':{'$ref':'#/components/schemas/Error'}}}} for code,desc in [(400,'Invalid request.'),(401,'Sign-in required.'),(403,'Active owner or resource check_in authority required.'),(404,'Feature disabled, booking unavailable, or malformed/unknown/foreign credential.'),(409,'Lifecycle, arrival or time-window conflict.'),(423,'Tenant frozen.'),(429,'Rate limit exceeded.'),(503,'Write gate unavailable.')]}
base = '/api/v1/public/{makerspace_slug}/my-bookings/{public_token}/'
for suffix, method, name, mime in [
 ('confirmation/','get','BookingConfirmation','application/json'),
 ('confirmation.png','get',None,'image/png'),
 ('calendar.ics','get',None,'text/calendar'),
 ('rotate-checkin/','post','BookingConfirmation','application/json'),
]:
 op={'operationId':'public_my_bookings_'+suffix.replace('/','').replace('.','_').replace('-','_')+'_'+method,
     'tags':['Member bookings'],'security':security,'parameters':[
       {'name':'makerspace_slug','in':'path','required':True,'schema':string},
       {'name':'public_token','in':'path','required':True,'schema':{'type':'string','format':'uuid'}}],
     'responses':{'200':{'description':'Private, no-store; Referrer-Policy no-referrer. Owner only.', 'content':{mime:{'schema':{'$ref':'#/components/schemas/'+name} if name else {'type':'string','format':'binary'}}}},**errors}}
 if method=='post': op['requestBody']={'content':{'application/json':{'schema':{'$ref':'#/components/schemas/EmptyAction'}}},'required':True}
 paths[base+suffix]={method:op}
for suffix, request in [('resolve/','BookingCredential'),('confirm/','BookingCredential'),('{booking_id}/reverse/','EmptyAction')]:
 parameters=[{'name':'id','in':'path','required':True,'schema':{'type':'integer'}}]
 if '{booking_id}' in suffix: parameters.append({'name':'booking_id','in':'path','required':True,'schema':{'type':'integer'}})
 paths['/api/v1/admin/spaces/{id}/arrival/'+suffix]={'post':{
   'operationId':'admin_spaces_arrival_'+suffix.replace('/','_').replace('{booking_id}','booking_id'),
   'tags':['Admin bookings'],'security':security,'parameters':parameters,
   'requestBody':{'content':{'application/json':{'schema':{'$ref':'#/components/schemas/'+request}}},'required':True},
   'responses':{'200':{'description':'Answer-free private scanner projection.', 'content':{'application/json':{'schema':{'$ref':'#/components/schemas/BookingArrival'}}}},**errors}}}
PATH.write_text(json.dumps(schema,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print('BK-C: 7 routes and typed confirmation/scanner/feature projections applied.')
