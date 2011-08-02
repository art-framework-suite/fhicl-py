#==========FHICLPY===============================================================================
# AUTHOR: Ryan Putz
# This is a python-based parser which utilizes the PyParsing module by Paul McGuire.
# It is a top-down, recursive descent parser.
# 
# CURRENT ISSUES: Recursion depth, hname association
# FIXED: Comments, Prolog Assembly, Includes, Refs
#================================================================================================
import sys, string, re
sys.path.append("/home/putz/fhicl/fhicl/fhicl-py")

#Make this more specific later
from pyparsing import *

#Reference storage
refs = {}
hnames = {}

#Exceptions
class ILLEGAL_STATEMENT(Exception):
     def __init__(self, stmt):
         self.msg = "Illegal Statement found before PROLOG: " + stmt
     def __str__(self):
         return repr(self.msg)

#Function for converting string to int
def convertInt(origString, loc, tokens):
   return int(tokens[0])

#Function for converting string to float
def convertFloat(origString, loc, tokens):
   return float(tokens[0])

#Updating hnames dict
def addHName(origString, loc, tokens):
   return tokens
   
#Function for processing the document
def addBraces(tokens):
   keys = []
   vals = []
   i = 0
   while i < (len(tokens)-1):
      #Assemble Prolog if found
      if str(tokens[i]).count("BEGIN_PROLOG") > 0:
         keys.append("PROLOG")
         vals.append(addBraces(tokens[i][1:(str(tokens).index("END_PROLOG"))]))
      #Else assemble doc body
      else:
         keys.append(tokens[i])
         #Found non-atom value
         if str(tokens[i + 1]) == ":":
            tokens.pop(i + 1)
            i += 1
            #Found a table
            if str(tokens[i]).count(":") > 0 and str(tokens[i]).count("@") == 0:
               vals.append(addBraces(tokens[i]))
            #Found a sequence    
            elif str(tokens[i]).count("[") > 0:
               vals.append(addBrackets(tokens[i]))
            #Found an atom
            else:
               if str(tokens[i]).count("@local::") > 0:
                  refs[tokens[(i-1)]] = tokens[i]
               vals.append(tokens[i])
         #Found an atom
         else:
            if str(tokens[i]).count("@local::") > 0:
               refs[tokens[(i-1)]] = tokens[i]
            vals.append(tokens[i])
      i += 1
   return dict(zip(keys,vals))        

#Function for handling sequences
def addBrackets(tokens):
   return tokens.asList()

#Forwarded Comment Definition
#Allows combined grammar to ignore commented lines
pcomment= Regex(r'\#.*')
ccomment= Regex(r'//.*')

#Rest of Grammar
def Syntax():
        #(Bottom)
        # --BOOLEAN--
        true= Word('true')
        false= Word('false')
        bool= true | false

        # --NUMBER--
        null= Word('nil')
        infinity= oneOf( 'infinity' '+infinity' '-infinity')
        integer= Regex(r'[1-9][0-9]*').setParseAction(convertInt) | Regex(r'[0-9]\w').setParseAction(convertInt)
        float= Regex(r'[0-9]*\.[0-9]*').setParseAction(convertFloat)
        hex= Regex(r'0x[\da-fA-F]*')
        sci= Regex(r'0-9.[0-9]*[e|E][0-9]*')
        simple= float | integer
        complex= Combine("(" + simple + "," + simple + ")")
        number= complex | simple | hex | sci | infinity
        
        # --STRING--
        dot= Regex(r'[.]')
        uquoted= Regex(r'[A-Za-z_][A-Za-z0-9_]*')
        squoted= Regex(r'\'[A-Za-z0-9]*\'')
        dquoted= Regex(r'"[A-Za-z0-9]*"')
        string= uquoted | squoted | dquoted
        name= uquoted
        #Added "Combine" to recognize hname token
        hname= Combine(name + OneOrMore(dot + name))   

        # --MISC--
        ws= Regex(r'\s*').suppress()
        ref= (Combine(Regex(r'@local::') + (hname | name)) | Combine( Regex(r'@db::') + (hname | hname)))

        # --ATOM|VALUE--
        atom= number | string | null | bool | ref
        #table & seq must be forwarded here so that a definition for value can be created
        table= Forward()
        seq= Forward()
        value= atom | table | seq

        # --ASSOCIATION--
        #name_assoc= name + (ws + Regex(r':') + ws) + value
        #association= name_assoc
        association= (hname | name) + (ws + Regex(r':') + ws) + value     

        # --SEQUENCE--
        seq_items= delimitedList(value, ",")
        seq_body= nestedExpr('[', ']', seq_items) 
        #filling in forwarded definition
        seq << seq_body

        # --TABLE--
        table_item= association | Regex(r'\s')
        table_items= OneOrMore(table_item)
        table_body= nestedExpr('{', '}', table_items)
        #filling in forwarded definition
        table<< table_body

        # --PROLOG--
        begin= Literal("BEGIN_PROLOG")
        end= Literal("END_PROLOG")
        prolog= Group(begin + Optional(table_items) + end)
        prologs= OneOrMore(prolog)

        # --DOCUMENT--
        doc_body= Optional(prolog) + Optional(table_items)
        document= doc_body
        return document
        #(Top)

#Is the passed line of input an include statement?
def isInclude(s):
        return (s.count("#include") and s.index("#include") == 0)

#Is the passed line of input a comment?
def isComment(s):
        return (s.count("#") > 0 or s.count(r'//') > 0) and not(isInclude(s))

def isHName(s):
        return s.count(".") > 0

#Reads External file and returns the contents
def handleInclude(s):
        name = s.split('"')
        name = name[1]
        file = open(name)
        fileContents = file.read()
        return fileContents

#Currently not used
def insertAfterProlog(ls, content):
        cont = content.splitlines(0)
        newContent = str("")
        i = 0
        while cont[i] != "END_PROLOG":
           newContent += cont[i]
           i += 1
        #Insert immediately after ENDPROLOG
        newContent += cont[i]
        i += 1
        for item in ls:
           cont.insert(i, item)
        ls.reverse()
        while i < len(cont):
           newContent += cont[i]
        return newContent

#Function to handle includes before grammar parsing begins      
def checkIncludes(s):
        #insertLater = []
        content = s.splitlines(0)
        pcontent = str("")
        i = 0
        while i < len(content)-1:
           #Checking for illegal statements before PROLOG
           #Comments are allowed
           if not(isComment(content[i])) and not(isInclude(content[i])) and content.count("BEGIN_PROLOG") > 0:
              j = content.index("BEGIN_PROLOG")
              if j > i:
                 raise ILLEGAL_STATEMENT(content[i])
           #Is the line an include?
           if isInclude(content[i]):
              fileContents = handleInclude(content[i])
              if fileContents.count("#include") > 0:
                 fileContents = handleInclude(fileContents)
              pcontent += fileContents
           #Otherwise just add it to the parsed content
           else:
              pcontent += content[i]
              pcontent += "\n"
           i += 1
        #return the parsed content
        return pcontent

#recursive handling of hname assignment
def recAssoc(dic, key, val):
   #Look for a DOT_INDEX token
   if key.count(".") > 0:
      #split off the leading name
      newKey = key.split(".", 1)
      #descend one level in the dictionary
      #and continue checking the rest of the hname
      return recAssoc(dic[newKey[0]], newKey[1])
   else:
      dic[key] = val
      return dic
#function for handling Left-Hand side Hnames
def handleHnameAssoc(dic):
   delItems = []
   for k, v in dic.iteritems():
      if isHName(k):
         key = k.split(".", 1)
         dic[key[0]] = recAssoc(dic[key[0]], key[1], v)
         delItems.append(k)
   for item in delItems:
      del dic[item]
   return dic
      
#Function for handling hnames in references.
def recRef(dic, key):
        #Look for a DOT_INDEX token
        if key.count(".") > 0:
           #split off the leading name
           newKey = key.split(".", 1)
           #descend one level in the dictionary
           #and continue checking the rest of the hname
           return recRef(dic[newKey[0]], newKey[1])
        else:
           return dic[key]

def handleRef(dic):
        # k = keys ; v = vals
        # iterating through the dictionary
        for k, v in refs.iteritems():
           #Grab the name being referenced (i.e. @local::<NAME>)
           newKey = v
           newKey = newKey.split("::")
           newKey = newKey[1]
           #VERSION 3:
           # If the newKey is an hierarchical name:
           if isHName(newKey):
              # Break off the first "chunk" (top-level name):
              newKey = newKey.split(".", 1)
              # Is the top-level name in the PROLOG?
              if "PROLOG" in dic and newKey[0] in dic["PROLOG"]:
                 dic[k] = recRef(dic["PROLOG"][newKey[0]], newKey[1])
              # Otherwise:
              else:
                 dic[k] = recRef(dic[newKey[0]], newKey[1])
           # Otherwise:
           else:
              # Is the key in the PROLOG?:
              if "PROLOG" in dic and newKey[0] in dic["PROLOG"]:
                 dic[k] = dic["PROLOG"][newKey]
              # Otherwise:
              else:
                 dic[k] = dic[newKey]

           #VERSION 2:
           #if "PROLOG" in dic and newKey[0] in dic["PROLOG"]:
           #   print "newKey: ", newKey
           #   if isHName(newKey):
           #      newKey = newKey.split(".", 1)
           #      dic[k] = recRef(dic["PROLOG"][newKey[0]], newKey[1], v)
           #   else:
           #      dic[k] = dic["PROLOG"][newKey]
           #else:
           #   if isHName(newKey):
           #      newKey = newKey.split(".", 1)
           #      dic[k] = recRef(dic[newKey[0]], newKey[1], v)
           #   else:
           #      dic[k] = dic[newKey]
        
           #VERSION 1:
           #hname check
           #NOTE: may be able to optimize this check
           #ISSUE: Hnames in PROLOG cause crash!
           #if newKey.count(".") > 0:
           #   prime the recursion
           #   newKey = newKey.split(".", 1)
           #   start recursive descent
           #   dic[k] = recRef(dic[newKey[0]], newKey[1], v)
           #check to see if the referenced key is in the PROLOG
           #Hnames in PROLOG are not supported here.
        
           #Checks to see if the dictionary has a PROLOG or not
           #elif "PROLOG" in dic:
           #   If the key exists in the PROLOG
           #   if newKey in dic["PROLOG"]:
           #      dic[k] = dic["PROLOG"][newKey]
           #indented in
           #else:
           #   dic[k] = dic[newKey]
        return dic

def isEmptyDoc(s):
        content = s.splitlines(0)
        if len(content) == 0:
           return False
        for line in content:
           if not(isComment(line)) and line != "":
              return False
        return True

def parse(s):
        doc = Syntax()
        #ignoring comments
        doc.ignore(ccomment)
        doc.ignore(pcomment)

        content = str("")
        #content = s
        #check for empty/only comments
        if isEmptyDoc(s):
           #If the document is empty, or just has comments/empty lines
           #Return an empty dictionary
           return dict()
        #includes checking
        if s.count("#include") > 0:
           s = checkIncludes(s)
        #parse contents of file
        docStr = doc.parseString(s)
        
        #convert over to proper dictionary
        docStr = addBraces(docStr)  
        
        #resolve hnames
        docStr = handleHnameAssoc(docStr)
        #resolve references
        docStr = handleRef(docStr)

        #removing PROLOG after resolving references
        if "PROLOG" in docStr:
           del docStr["PROLOG"]
        return docStr

if __name__ == '__main__':
        contents = sys.stdin.read()
        d= parse(contents)
        print d
