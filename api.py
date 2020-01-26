import flask
from flask import request
import json,requests

app = flask.Flask(__name__)
app.config["DEBUG"] = True

@app.route('/', methods=['GET'])
def home():
    text = str(request.args.get('text'))
    debug=False
    resp={}
    main_url = "https://luis-final.cognitiveservices.azure.com/luis/prediction/v3.0/apps/07c0c9aa-7815-4e09-92da-787ab7310d20/slots/staging/predict?subscription-key=3050a2b8146f4ea987465805faa49592&verbose=true&show-all-intents=true&log=true&query="
    trailing_subs=[" in the"," of the", " in"," and" ," and then"," on the"," on"," then"," to"," from"," instead"]
    if text.endswith("\n"):
        text=text[:-1]
    url=main_url+text
    response = requests.request('GET',url)
    u=json.loads(response.text)

    top_intent=u['prediction']['topIntent']
    top_score=u['prediction']['intents'][u['prediction']['topIntent']]['score']
    resp['text']=text
    resp['top_intent']=top_intent
    if debug:resp['top_score']=top_score

    entities=[]
    sub_entities=[]
    hier_entities=[]
    hierarchy=['typeofnav_section', 'typeofnav_question', 'typeofnav_subpart', 'typeofnav_answer', 'typeofnav_chapter', 'typeofnav_page', 'typeofnav_passage', 'typeofnav_rough', 'typeofnav_step', 'typeofnav_paragraph', 'typeofnav_sentence']
    entity_lis=[]
    entity_pos=[]
    entity_copy=[]
    entity_resolve_nav=[]
    pos_resolve_nav=[]
    ## Resolving for description:
    for entity in list(u['prediction']['entities'].keys())[:-1]:
        for i in range(len(u['prediction']['entities']["$instance"][entity])):
            ent=u['prediction']['entities']["$instance"][entity][i]['type']
            if "typeofnav" in ent:
                entity_lis.append(ent)
                entity_pos.append(u['prediction']['entities']["$instance"][entity][i]['startIndex'])  
            if "typeofnav" in ent or "description_nav" in ent :
                entity_resolve_nav.append(ent)
                pos_resolve_nav.append(u['prediction']['entities']["$instance"][entity][i]['startIndex'])  

    yx = zip(entity_pos, entity_lis)
    entity_lis = [x for y, x in yx]
    entity_copy=list(entity_lis)

    yx = zip(pos_resolve_nav, entity_resolve_nav)
    entity_resolve_nav = [x for y, x in yx]

    previous_flag=False
    next_flag=False
    nav_flag=False

    ## Entity Extraction   
    for entity in list(u['prediction']['entities'].keys())[:-1]:
        ## Father Entities (all except ordinal and number)
        for i in range(len(u['prediction']['entities']["$instance"][entity])):
            father_entity={}
            ent=u['prediction']['entities']["$instance"][entity][i]['type']
            tex=u['prediction']['entities']["$instance"][entity][i]['text']
            if "list" in ent or "." in ent:continue ## not printing list entities (exact matches)     
            if "description" in ent: ## Removing trailing subs
                for sub_t in trailing_subs:
                    if tex.endswith(sub_t):
                        tex=tex[:tex.rindex(sub_t)]  

    ## Resolution of description entities (linking them with there parent entity)
            if "description1" in ent:
                ent=entity_lis[0].split("_")[1]+"_description"
                entity_copy.remove(entity_lis[0])
            if "description2" in ent:
                ent=entity_lis[1].split("_")[1]+"_description"
                entity_copy.remove(entity_lis[1])

            if "description_nav" in ent:
                ind=entity_resolve_nav.index("description_nav")
                ent=entity_resolve_nav[(ind-1)].split("_")[1]+"_description"
                entity_copy.remove(entity_resolve_nav[(ind-1)])

    ## Rule based previous and next entities to be linked later
            if "previous" in ent:
                previous_flag=True
                continue
            if "next" in ent:
                next_flag=True
                continue

            if "typeofnav_" or "rough" in ent:
                nav_flag=True
            father_entity['entity']=ent
            father_entity['value']=tex
            ## some entities do not have score(Previous and next)
            if debug:
                try:
                    score=u['prediction']['entities']["$instance"][entity][i]['score']
                    father_entity['score']=score
                except : pass
    ##Saving entity in there respective lists to resolve later
            if "description" in ent and not("write" in ent or "delete" in ent or "note" in ent or "reminder" in ent):
                sub_entities.append(father_entity)
                continue

            if ent in hierarchy:
                hier_entities.append(father_entity)
                continue
            entities.append(father_entity)

    #child entity (ordinal and number)
        try:
            if not "." in ent:
                for c in range(len(u['prediction']['entities'][entity])):
                    for child in list(u['prediction']['entities'][entity][i].keys())[:-1]:
                        child_entity={}
                        ent=child
                        tex=u['prediction']['entities'][entity][c]["$instance"][child][0]['text']
                        score=u['prediction']['entities'][entity][c]["$instance"][child][0]['score']
                        child_entity['entity']=ent
                        child_entity['value']=tex
                        if debug: child_entity['score']=score
                        entity_copy.remove(("typeofnav_"+ent.split("_")[0]))
                        sub_entities.append(child_entity)
        except:pass
        
    if previous_flag and len(entity_copy)>=1:
        child_entity={} 
        for en in hierarchy:
            if en in entity_copy:
                child_entity['entity']=en.split("_")[1]+'_ordinal'
        child_entity['value']="previous"
        sub_entities.append(child_entity)
    if next_flag and len(entity_copy)>=1:
        child_entity={}
        for en in hierarchy:
            if en in entity_copy:
                child_entity['entity']=en.split("_")[1]+'_ordinal'
#         child_entity['entity']=entity_copy[0].split("_")[1]+'_ordinal'
        child_entity['value']="next"
        sub_entities.append(child_entity)

    for ij in hierarchy:
        for jk in hier_entities:
            if jk['entity']==ij:
                for kl in sub_entities:
                    if kl['entity'].split('_')[0] in ij:
                        jk['CHILD']=kl
                        break
                entities.append(jk)

    resp['Entities']=entities
    #when other intents act like Navigation
    if ((resp['top_intent']=="Repeat" or resp['top_intent']=="speed" ) and nav_flag ) or "Navigation" in resp['top_intent']:
        resp["top_intent"]="Navigation"
    #Dividing note vs reminder
    if resp["top_intent"]=="Note":
        for i in resp['Entities']:
            if i['entity']=='nav_reminder':
                resp['top_intent']='Reminder'
    #dividing Meta to- #questions vs marks vs time
    if resp["top_intent"]=='META':
        for i in resp['Entities']:
            if i['entity']=='meta_time':
                resp["top_intent"]='time_check'
                resp['Entities']=[]
                break
            if i['entity']=='meta_marks':
                resp["top_intent"]='marks_check'
                resp['Entities'].remove(i)
                break
    return(str(resp))
app.run()