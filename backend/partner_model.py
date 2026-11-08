"""Small deterministic logistic regression, implemented with the standard library."""
from __future__ import annotations
import csv, math, random
from functools import lru_cache
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CAT_FIELDS=("segment","has_gstin","city_tier","lead_source")
NUM_FIELDS=("employee_count","num_sites","monthly_telecom_spend_inr")

def _sigmoid(x): return 1/(1+math.exp(-max(-30,min(30,x))))
def _features(rows, schema):
    cats,numeric=schema;out=[]
    for r in rows:
        v=[1.0]
        for field,values in cats:
            if field=="products_of_interest":tokens=set(str(r.get(field,"")).split(";"))
            else:tokens={str(r.get(field,""))}
            v.extend(float(token in tokens) for token in values)
        for field,mean,sd in numeric:
            try:n=max(0,float(r.get(field) or 0))
            except ValueError:n=0
            if field=="monthly_telecom_spend_inr":n=math.log1p(n)
            v.append((n-mean)/sd)
        out.append(v)
    return out

def train(rows):
    """80/20 chronological-free holdout; return model, holdout AUC, ranked features."""
    clean=[r for r in rows if r.get("outcome","").lower() in {"activated","dropped"}]
    rng=random.Random(2026);order=list(range(len(clean)));rng.shuffle(order);cut=max(1,int(len(order)*.8));train=[clean[i] for i in order[:cut]];test=[clean[i] for i in order[cut:]]
    cats=[]
    for f in CAT_FIELDS+("products_of_interest",):
        vals=set()
        for r in train:
            if f=="products_of_interest":vals.update(x for x in r.get(f,"").split(";") if x)
            elif r.get(f):vals.add(str(r[f]))
        cats.append((f,sorted(vals)))
    numeric=[]
    for f in NUM_FIELDS:
        vals=[]
        for r in train:
            try:n=max(0,float(r.get(f) or 0))
            except ValueError:n=0
            vals.append(math.log1p(n) if f=="monthly_telecom_spend_inr" else n)
        mean=sum(vals)/max(1,len(vals));sd=math.sqrt(sum((x-mean)**2 for x in vals)/max(1,len(vals))) or 1
        numeric.append((f,mean,sd))
    schema=(cats,numeric);x=_features(train,schema);y=[float(r["outcome"].lower()=="activated") for r in train];w=[0.0]*len(x[0]);lr=.18
    for epoch in range(220):
        grad=[0.0]*len(w)
        for row,target in zip(x,y):
            p=_sigmoid(sum(a*b for a,b in zip(w,row)));err=p-target
            for j,val in enumerate(row):grad[j]+=err*val
        for j in range(len(w)):w[j]-=lr*(grad[j]/len(x)+(.02*w[j] if j else 0))
    xt=_features(test,schema);yt=[float(r["outcome"].lower()=="activated") for r in test];scores=[_sigmoid(sum(a*b for a,b in zip(w,row))) for row in xt]
    pos=sorted(s for s,t in zip(scores,yt) if t);neg=sorted(s for s,t in zip(scores,yt) if not t)
    auc=(sum(sum(1 for n in neg if p>n)+.5*sum(1 for n in neg if p==n) for p in pos)/(len(pos)*len(neg))) if pos and neg else 0.0
    labels=["intercept"]
    for field,values in cats:labels.extend(f"{field}={v}" for v in values)
    labels.extend(field for field,_,_ in numeric)
    importance=sorted(({"feature":name,"weight":round(weight,4)} for name,weight in zip(labels[1:],w[1:])),key=lambda a:abs(a["weight"]),reverse=True)
    return {"schema":schema,"weights":w,"auc":round(auc,4),"features":importance[:10],"train_rows":len(train),"test_rows":len(test)}

def predict(rows,model):
    values=_features(rows,model["schema"])
    return [_sigmoid(sum(a*b for a,b in zip(model["weights"],row))) for row in values]

@lru_cache(maxsize=1)
def get_model():
    with (ROOT/"data"/"smb_leads.csv").open(encoding="utf-8-sig",newline="") as f:return train(list(csv.DictReader(f)))

if __name__=="__main__":
    result=get_model();print(f"Holdout AUC: {result['auc']:.4f} ({result['test_rows']} leads)");print("Top features:")
    for x in result["features"]:print(f"  {x['feature']}: {x['weight']:+.4f}")
