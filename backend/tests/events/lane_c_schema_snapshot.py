"""Update the snapshot from the Lane C DRF declarations on hosts without Django."""
from copy import deepcopy
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
p = ROOT / 'frontend/openapi-schema.json'
s = json.loads(p.read_text(encoding='utf-8'))
c, paths = s['components']['schemas'], s['paths']
def ref(name): return {'$ref': '#/components/schemas/' + name}
def obj(props, required=None): return {'type': 'object', 'properties': deepcopy(props), 'required': sorted(props) if required is None else required}
def response(name): return {'description': '', 'content': {'application/json': {'schema': ref(name)}}}
text, integer, boolean = {'type':'string'}, {'type':'integer'}, {'type':'boolean'}
date={'type':'string','format':'date-time'}
visibility={'type':'string','enum':['draft','published'],'default':'draft'}
section={'kind': {'type':'string','enum':['intro','logo','speaker','track','room','sponsor','faq','resource','highlight']},
 'slug': {**text,'maxLength':80,'pattern':'^[-a-zA-Z0-9_]+$'}, 'title':{**text,'maxLength':200},
 'body':{**text,'maxLength':10000,'default':''},'url':{**text,'format':'uri','maxLength':500,'default':''},
 'asset_id':{**integer,'nullable':True,'minimum':1,'default':None},'visibility':visibility,
 'position':{**integer,'minimum':0,'maximum':1000,'default':0}}
section.update({
 'headline':{**text,'maxLength':200}, 'organization':{**text,'maxLength':200},
 **{key:{**text,'format':'uri','maxLength':500} for key in ['website_url','linkedin_url','x_url']},
 'sponsor_tier':{**text,'enum':['platinum','gold','silver','partner','community_partner']},
 'icon':{**text,'maxLength':40}})
groups=['HERO','ABOUT','HIGHLIGHTS','SCHEDULE','SPEAKERS','SPONSORS','VENUE','FAQ','RESOURCES']
venue={key:{**text,'maxLength':limit,'default':''} for key,limit in {
 'name':200,'address':500,'city':200,'country':200,'directions':2000,'parking':2000,
 'public_transport':2000,'accessibility_notes':2000}.items()}
venue.update({key:{'type':'number','format':'double','minimum':-limit,'maximum':limit,'nullable':True,'default':None}
 for key,limit in [('latitude',90),('longitude',180)]})
venue['map_url']={**text,'format':'uri','maxLength':500,'default':''}
c['WebsiteVenue']=obj(venue,[])
metadata={'tagline':{**text,'maxLength':300},
 'accent_color':{**text,'pattern':'^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$'},
 'section_order':{'type':'array','items':{**text,'enum':groups},'minItems':len(groups),'maxItems':len(groups),
                  'description':'Each canonical page group exactly once, in display order.'},
 'section_enabled':{'type':'object','additionalProperties':boolean,
                    'description':'Canonical page groups only; omitted groups are enabled. Public projection, direct pages and image serving honor disabled groups.'},
 'venue':{'allOf':[ref('WebsiteVenue')],'nullable':True}}
session={'slug':section['slug'],'title':section['title'],'body':section['body'],'starts_at':date,'ends_at':date,
 'track':{**section['slug'],'nullable':True,'default':None},'room':{**section['slug'],'nullable':True,'default':None},
 'speakers':{'type':'array','maxItems':20,'items':section['slug'],'default':[]},'visibility':visibility}
c['WebsiteSectionInput']=obj(section,['kind','slug','title'])
c['WebsiteSessionInput']=obj(session,['slug','title','starts_at','ends_at'])
c['WebsiteContentInput']=obj({'revision':{**integer,'minimum':0},'sections':{'type':'array','maxItems':100,'items':ref('WebsiteSectionInput')},'sessions':{'type':'array','maxItems':200,'items':ref('WebsiteSessionInput')}})
c['WebsiteContentInput']['properties'].update(deepcopy(metadata))
c['WebsiteContentInput']['properties']['sections']['description']='At most 30 room sections. Omitted profile/tier/icon fields preserve the same-slug section values; new rows default to blank profile/icon and community_partner. Speaker photos and sponsor logos use page-owned private asset IDs.'
c['WebsiteReleaseInput']=obj({'released':boolean,'revision':{**integer,'minimum':1}})
c['WebsiteDelayInput']=obj({'delay_minutes':{**integer,'minimum':0,'maximum':1440}})
c['WebsiteAssetInput']=obj({'file':{**text,'format':'binary'},'alt_text':{**text,'maxLength':200},'replace_id':{**integer,'minimum':1}},['file','alt_text'])
c['WebsiteAsset']=obj({'id':integer,'alt_text':text,'size_bytes':integer})
c['WebsiteSection']=obj({**section,'image_url':{**text,'nullable':True},'image_alt_text':text},['kind','slug','title','image_url','image_alt_text'])
c['WebsiteSession']=obj({**session,'delay_minutes':integer,'effective_starts_at':date,'effective_ends_at':date},['slug','title','starts_at','ends_at','delay_minutes','effective_starts_at','effective_ends_at'])
c['Website']=obj({'revision':integer,'released':boolean,'inherited':boolean,'sections':{'type':'array','items':ref('WebsiteSection')},'sessions':{'type':'array','items':ref('WebsiteSession')},'assets':{'type':'array','items':ref('WebsiteAsset')}},['revision','released','inherited','sections','sessions'])
c['Website']['properties'].update(deepcopy(metadata))
c['WebsiteOrigins']=obj({'origins':{'type':'array','maxItems':20,'items':{**text,'maxLength':255}}})
c['EventWebsitePublishInput']=obj({'publish_website':{**boolean,'default':False},'website_revision':{**integer,'minimum':1}},[])
c['PublicEvent']['properties']['website']={'allOf':[ref('Website')],'nullable':True,'readOnly':True}
c['PublicEvent']['required']=sorted(set(c['PublicEvent'].get('required',[]))|{'website'})
c['EventSeriesDetail']['properties']['website_enabled']={**boolean,'readOnly':True}
c['EventSeriesDetail']['required']=sorted(set(c['EventSeriesDetail'].get('required',[]))|{'website_enabled'})
card={k:text for k in ['title','description','date','location','availability','audience_label','revision','makerspace_name']}
card.update({'url':{**text,'format':'uri'},'image_url':{**text,'format':'uri','nullable':True},'registration_count':{**integer,'nullable':True}})
c['DiscoveryCard']=obj(card)
c['Discovery']=obj({'count':integer,'next':{**text,'format':'uri','nullable':True},'previous':{**text,'format':'uri','nullable':True},'results':{'type':'array','items':ref('DiscoveryCard')}})
prototype=paths['/api/v1/admin/events/{id}/']['get']
def add(path, method, output=None, body=None, public=False, code=200, mime='application/json', description=''):
 op={'operationId': 'lane_c_'+path.strip('/').replace('/','_').replace('{','').replace('}','').replace('-','_').replace('.','_')+'_'+method,
     'tags':['Public websites' if public else 'Event website'], 'description':description,
     'parameters':[], 'responses':{str(n):response('Error') for n in ([404,429] if public else [400,401,403,404,429,503])}}
 for part in path.split('/'):
  if part.startswith('{'):
   name=part[1:-1]; field=integer if name in {'id','asset_id','makerspace_id'} else {**text,'format':'uuid'} if name=='public_token' else text
   op['parameters'].append({'in':'path','name':name,'schema':field,'required':True})
 if not public: op['security']=deepcopy(prototype['security'])
 if code==204: op['responses']['204']={'description':'Removed.'}
 elif mime=='application/json': op['responses'][str(code)]=response(output)
 else: op['responses'][str(code)]={'description':description,'content':{mime:{'schema':{**text,**({'format':'binary'} if mime=='image/webp' else {})}}}}
 if body: op['requestBody']={'required':True,'content':{('multipart/form-data' if body=='WebsiteAssetInput' else 'application/json'):{'schema':ref(body)}}}
 paths.setdefault(path,{})[method]=op
 return op
for kind in ['events','event-series']:
 base='/api/v1/admin/'+kind+'/{id}/website/'
 desc='Live event/series edit_details for sections/assets; publish_schedule for programme, delays and release. Feature events.website is required. Draft pages are private; series inheritance uses copy-on-write with independent private assets. Revisions refuse stale editor writes.'
 add(base,'get','Website',description=desc)
 add(base,'put','Website','WebsiteContentInput',description=desc)
 add(base+'release/','post','Website','WebsiteReleaseInput',description=desc)
 add(base+'sessions/{slug}/delay/','post','Website','WebsiteDelayInput',description=desc)
 add(base+'assets/','post','WebsiteAsset','WebsiteAssetInput',code=201,description=desc+' Bounded JPEG/PNG/WebP upload; bytes sniffed, re-encoded and stored privately, no object keys accepted or returned.')
 add(base+'assets/{asset_id}','get',mime='image/webp',description='Authorized private WebP preview; no-store.')
 add(base+'assets/{asset_id}','delete',code=204,description=desc)
base='/api/v1/public/{makerspace_slug}/events/{public_token}/website/'
for suffix,output in [('', 'Website'),('sections/{slug}/','WebsiteSection'),('sessions/{slug}/','WebsiteSession')]:
 add(base+suffix,'get',output,public=True,description='Published, public, unexpired, servable event plus enabled events.website and released effective page. Only explicitly published items; uniform 404 otherwise. No-store.')
schedule = add(base+'schedule/','get','WebsiteSession',public=True,description='Live-gated released programme; published sessions and visible relations only.')
schedule['responses']['200']['content']['application/json']['schema']={'type':'array','items':ref('WebsiteSession')}
add(base+'speakers/{slug}/','get','WebsiteSection',public=True,description='Live-gated released speaker; draft or non-speaker slugs are uniform 404.')
add(base+'assets/{asset_id}/','get',public=True,mime='image/webp',description='Live-gated, released, referenced private WebP image. Unreleased, draft-only, foreign and missing images are uniform 404; no-store.')
add('/embed/{makerspace_slug}/{kind}/{public_token}/','get',public=True,mime='text/html',description='Backend card for a released website. Exact HTTPS tenant framing origins, events.embed and events.website required. Empty origin list fails closed. No-store.')
add('/share/{kind}/{public_token}/','get',public=True,mime='text/html',description='Noindex OG/Twitter HTML using public cover only. Checks current visibility before every cache read; server content cache 600s, browser revalidation required.')
op=add('/api/v1/discover/{kind}/','get','Discovery',public=True,description='Deployment-local directory-consenting public subjects, 24 per page. Domain adapter owns lifecycle rules; event counts follow show_registration_count.')
op['parameters'] += [{'in':'query','name':k,'schema':v} for k,v in {'q':{**text,'maxLength':200},'date_from':{**text,'format':'date'},'date_to':{**text,'format':'date'},'page':{**integer,'minimum':1}}.items()]
op['responses']['400']=response('Error')
add('/sitemap.xml','get',public=True,mime='application/xml',description='Live-gated, edition-aware canonical public URLs for this verified tenant origin or the central directory; no-store.')
add('/robots.txt','get',public=True,mime='text/plain',description='Known-origin crawler rules and sitemap URL.')
for method in ['get','put']:
 add('/api/v1/admin/makerspaces/{makerspace_id}/website-embed-origins/',method,'WebsiteOrigins','WebsiteOrigins' if method=='put' else None,description='Tenant MANAGE_MAKERSPACE required. Separate framing trust; at most twenty canonical exact HTTPS origins, no credentials, paths, wildcards or default ports. Empty disables embedding. Audited.')
paths['/api/v1/admin/events/{id}/publish/']['post']['requestBody']={'content':{'application/json':{'schema':ref('EventWebsitePublishInput')}}}
p.write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print('Lane C OpenAPI snapshot updated from view/serializer contracts.')
