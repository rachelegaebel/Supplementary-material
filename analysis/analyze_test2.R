
# Test 2 - reproducible analysis (R version) -- RacqI vs naked, blind rater study
# Mirrors analyze_test2.py and reproduces the same numbers.
#
# No external packages required (Krippendorff's alpha implemented in base R).
# Set BASE to the Test2_dataset folder, then: source("analyze_test2.R")
#
# The de-blinding mapping below (block,pos -> id,density,racqi_label) is the
# pre-registered key, VERIFIED against the actual answer text of both surveys
# (see the PASS check in analyze_test2.py). It is embedded here so R needs no
# JSON dependency and the mapping is transparent.


BASE <- "/Users/rache/Library/Mobile Documents/com~apple~CloudDocs/Bocconi/Tesi/Test2_dataset"

## de-blinding key 
keymap <- read.csv(text="
block,pos,id,density,racqi_label
A,1,01,dense,B
A,2,13,control,A
A,3,05,dense,A
A,4,08,thin,B
B,1,02,thin,B
B,2,14,control,A
B,3,09,dense,A
B,4,12,thin,B
C,1,10,thin,A
C,2,03,dense,A
C,3,15,control,B
C,4,06,thin,A
D,1,16,control,B
D,2,07,dense,A
D,3,04,thin,A
D,4,11,dense,A
", header=TRUE, colClasses="character", strip.white=TRUE)
kget <- function(B, pos) keymap[keymap$block==B & keymap$pos==pos, ]

## QID layouts (fixed by the survey structure) 
# experts: per block, 4 pairs (answerA_qid, answerB_qid); dims _1=reasoning, _2=evidence
exp_layout <- list(
  A=list(c(4,6),c(8,10),c(12,14),c(16,18)), B=list(c(21,23),c(25,27),c(29,31),c(33,35)),
  C=list(c(38,40),c(42,44),c(46,48),c(50,52)), D=list(c(55,57),c(59,61),c(63,65),c(67,69)))
# non-experts: per block, 4 triples (answerA, answerB, forced); dims _1=trust,_2=action,_3=compet
ne_layout <- list(
  A=list(c(4,6,7),c(9,11,12),c(14,16,17),c(19,21,22)), B=list(c(25,27,28),c(30,32,33),c(35,37,38),c(40,42,43)),
  C=list(c(46,48,49),c(51,53,54),c(56,58,59),c(61,63,64)), D=list(c(67,69,70),c(72,74,75),c(77,79,80),c(82,84,85)))

## robust Qualtrics loader 
load_qualtrics <- function(path){
  lines <- readLines(path, warn=FALSE)
  h <- which(startsWith(lines, "StartDate"))[1]           # the codes header row
  df <- read.csv(path, sep=";", skip=h-1, header=TRUE, colClasses="character", check.names=FALSE)
  df[-c(1,2), , drop=FALSE]                                # drop IT-labels + ImportId rows
}
num <- function(x){ x[x==""] <- NA; suppressWarnings(as.integer(x)) }

## de-blind -> long tables 
deblind_experts <- function(df){
  out <- list()
  for(B in names(exp_layout)) for(pos in seq_along(exp_layout[[B]])){
    it <- kget(B,pos); qa <- exp_layout[[B]][[pos]][1]; qb <- exp_layout[[B]][[pos]][2]
    for(lab in c("A","B")){
      q <- if(lab=="A") qa else qb
      rea <- num(df[[paste0("QID",q,"_1")]]); evi <- num(df[[paste0("QID",q,"_2")]])
      keep <- !(is.na(rea) & is.na(evi))
      if(any(keep)) out[[length(out)+1]] <- data.frame(
        rater=df$ResponseId[keep], id=it$id, density=it$density,
        arm=if(lab==it$racqi_label) "RacqI" else "naked",
        reasoning=rea[keep], evidence=evi[keep], stringsAsFactors=FALSE)
    }
  }
  do.call(rbind, out)
}
deblind_nonexperts <- function(df){
  out <- list(); fc <- list()
  for(B in names(ne_layout)) for(pos in seq_along(ne_layout[[B]])){
    it <- kget(B,pos); tr <- ne_layout[[B]][[pos]]; qa<-tr[1]; qb<-tr[2]; qf<-tr[3]
    for(lab in c("A","B")){
      q <- if(lab=="A") qa else qb
      tru<-num(df[[paste0("QID",q,"_1")]]); act<-num(df[[paste0("QID",q,"_2")]]); com<-num(df[[paste0("QID",q,"_3")]])
      keep <- !(is.na(tru) & is.na(act) & is.na(com))
      if(any(keep)) out[[length(out)+1]] <- data.frame(
        rater=df$ResponseId[keep], id=it$id, density=it$density,
        arm=if(lab==it$racqi_label) "RacqI" else "naked",
        trust=tru[keep], action=act[keep], compet=com[keep], stringsAsFactors=FALSE)
    }
    fvraw <- df[[paste0("QID",qf)]]; sel <- fvraw %in% c("1","2")
    if(any(sel)){
      chosen <- ifelse(fvraw[sel]=="1","A","B")
      fc[[length(fc)+1]] <- data.frame(id=it$id, density=it$density,
        chose_racqi=as.integer(chosen==it$racqi_label), stringsAsFactors=FALSE)
    }
  }
  list(tidy=do.call(rbind,out), fc=do.call(rbind,fc))
}

## per-condition aggregates 
aggregates <- function(df, dims){
  res <- data.frame()
  for(dim in dims) for(dens in c("dense","thin","control")) for(arm in c("RacqI","naked")){
    s <- df[df$density==dens & df$arm==arm, dim]; s <- s[!is.na(s)]
    d <- sapply(1:5, function(k) round(mean(s==k)*100))
    res <- rbind(res, data.frame(dim=dim, density=dens, arm=arm, n=length(s),
      mean=round(mean(s),2), median=median(s),
      iqr=paste0(quantile(s,.25),"-",quantile(s,.75)),
      pct1=d[1],pct2=d[2],pct3=d[3],pct4=d[4],pct5=d[5]))
  }
  res
}

## contrasts + gradient + retention
contrasts <- function(E,N,FC){
  dm <- function(df,i,a,dim) mean(df[df$id==i & df$arm==a, dim], na.rm=TRUE)
  ids <- sort(unique(E$id)); R <- data.frame()
  for(i in ids){
    R <- rbind(R, data.frame(id=i, density=E$density[E$id==i][1],
      d_evidence =dm(E,i,"RacqI","evidence") -dm(E,i,"naked","evidence"),
      d_reasoning=dm(E,i,"RacqI","reasoning")-dm(E,i,"naked","reasoning"),
      d_trust    =dm(N,i,"RacqI","trust")    -dm(N,i,"naked","trust"),
      d_action   =dm(N,i,"RacqI","action")   -dm(N,i,"naked","action"),
      d_compet   =dm(N,i,"RacqI","compet")   -dm(N,i,"naked","compet"),
      racqi_choice_pct = mean(FC$chose_racqi[FC$id==i])*100))
  }
  R
}

## Krippendorff's alpha (ordinal) -- base R, no dependency 
kripp_ordinal <- function(units){
  units <- units[sapply(units, length) >= 2]
  vals <- sort(unique(unlist(units))); K <- length(vals)
  idx <- setNames(seq_along(vals), as.character(vals))
  o <- matrix(0, K, K)
  for(u in units){ m <- length(u)
    for(i in seq_len(m)) for(j in seq_len(m)) if(i!=j){
      a <- idx[[as.character(u[i])]]; b <- idx[[as.character(u[j])]]; o[a,b] <- o[a,b] + 1/(m-1) } }
  nc <- rowSums(o); n <- sum(nc)
  d2 <- function(a,b){ lo<-min(a,b); hi<-max(a,b); s <- sum(nc[lo:hi]) - (nc[a]+nc[b])/2; s*s }
  Do <- sum(outer(1:K,1:K, Vectorize(function(a,b) o[a,b]*d2(a,b))))
  De <- sum(outer(1:K,1:K, Vectorize(function(a,b) nc[a]*nc[b]*d2(a,b)))) / (n-1)
  1 - Do/De
}
alpha_for <- function(df, dim){
  d <- df[!is.na(df[[dim]]), ]
  units <- split(d[[dim]], paste(d$id, d$arm))          # per (id,arm): vector of ratings
  round(kripp_ordinal(units), 3)
}

## controls attribution (3-case rule) 
controls_attr <- function(E){
  txt <- paste(readLines(file.path(BASE,"DATASET_32_normalized.md"), warn=FALSE), collapse="\n")
  chunks <- strsplit(txt, "### \\[", perl=TRUE)[[1]]
  names <- c("13"="Branding","14"="Design/build","15"="Acoustics","16"="Sales")
  res <- data.frame()
  for(id in names(names)){
    ch <- chunks[startsWith(chunks, paste0(id,"] · RacqI-Claude"))]
    if(length(ch)==0) next
    cites <- regmatches(ch[1], gregexpr("\\([A-Z][^()]{2,60}?\\)", ch[1], perl=TRUE))[[1]]
    cites <- unique(cites[grepl("[A-Za-z]{4,}", cites) & !grepl("^\\((RSI|see|Catchment|Lookup)\\)$", cites)])
    de <- mean(E[E$id==id & E$arm=="RacqI","evidence"],na.rm=TRUE) - mean(E[E$id==id & E$arm=="naked","evidence"],na.rm=TRUE)
    res <- rbind(res, data.frame(id=id, control=names[[id]], distinct_sources=length(cites),
      d_evidence=round(de,2), case=ifelse(length(cites)>=2,"b: curated grounding","a/other")))
  }
  res
}

## ============================ run ===========================================
exp_csv <- list.files(BASE, "Test 2 - Experts_.*\\.csv$", full.names=TRUE)
ne_csv  <- list.files(BASE, "Test 2 - Non-experts_.*\\.csv$", full.names=TRUE)
E  <- deblind_experts(load_qualtrics(exp_csv[length(exp_csv)]))
NN <- deblind_nonexperts(load_qualtrics(ne_csv[length(ne_csv)])); N <- NN$tidy; FC <- NN$fc

cat("experts:", length(unique(E$rater)), "raters,", nrow(E), "answer-ratings |",
    "non-experts:", length(unique(N$rater)), "raters,", nrow(N), "answer-ratings,", nrow(FC), "forced choices\n\n")

cat("== per-condition aggregates (experts) ==\n");     print(aggregates(E, c("evidence","reasoning")), row.names=FALSE)
cat("\n== per-condition aggregates (non-experts) ==\n"); print(aggregates(N, c("trust","action","compet")), row.names=FALSE)

R <- contrasts(E,N,FC)
grad <- aggregate(cbind(d_evidence,d_reasoning,d_trust,d_action,d_compet,racqi_choice_pct)~density, R, mean)
cat("\n== gradient (mean RacqI-naked contrast by density) ==\n"); print(grad, row.names=FALSE, digits=3)
ret <- round(grad[grad$density=="thin",-1] / grad[grad$density=="dense",-1] * 100)
cat("\n== retention thin/dense (%) = the dissociation ==\n"); print(ret, row.names=FALSE)

cat("\n== Krippendorff alpha (ordinal) ==\n")
cat("experts    : evidence", alpha_for(E,"evidence"), "| reasoning", alpha_for(E,"reasoning"), "\n")
cat("non-experts: trust", alpha_for(N,"trust"), "| action", alpha_for(N,"action"), "| compet", alpha_for(N,"compet"), "\n")

cat("\n== controls attribution (3-case rule) ==\n"); print(controls_attr(E), row.names=FALSE)
