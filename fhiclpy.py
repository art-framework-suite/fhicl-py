#==========FHICLPY===============================================================================
# AUTHOR: Ryan Putz
# This is a python-based parser which utilizes the PyParsing module by Paul McGuire.
# It is a top-down, recursive descent parser.
# 
# CURRENT ISSUES: Dictionary is insufficient for this useage--
#       Feature: incorrect output for test case:
#               tab:{ a:1 } tab.a:2 a:@local::tab.a
#       Expected Output: { a:2 tab:{ a:2 }}
#       Actual Output  : { a:1 tab:{ a:1 }}
# FIXED: Comments, Prolog Assembly, Includes, Refs
#================================================================================================
import sys, string, re, decimal
import os.path
sys.path.append("/home/putz/fhicl/fhicl/fhicl-py")
sys.path.append("/home/putz/fhicl/fhicl/fhicl-py/orderedDict.py")

#Make this more specific later
from pyparsing import *
from orderedDict import OrderedDict
from decimal import *

#Reference storage
delItems = []
errLoc = 0
parseExceptions = []

#Exceptions
class INVALID_KEY(Exception):
   def __init__(self, stmt):
      self.msg = stmt
   def __str__(self):
      return repr(self.msg)

class INVALID_INCLUDE_SYNTAX(Exception):
   def __init__(self, stmt):
      self.msg = stmt
   def __str__(self):
      return repr(self.msg)

class PARSE_FAILURE(ParseSyntaxException):
   def __init__(self, stmt):
      self.msg = stmt
   def __str__(self):
      return repr(self.msg)

class ILLEGAL_STATEMENT(Exception):
   def __init__(self, stmt, i):
      self.msg = "Illegal statement found before PROLOG at line " + str(i) + " => " + stmt
   def __str__(self):
      return repr(self.msg)

class INVALID_ASSOCIATION(Exception):
   def __init__(self, stmt):
      self.msg = stmt
   def __str__(self):
      return repr(self.msg)

def invalidAssoc(origString, loc, tokens):
    exc = INVALID_ASSOCIATION("No value for association ")
    parseExceptions.append(exc)
    return tokens

#joining two dicts (recursive)
def join(A, B):
    if not isinstance(A, dict) or not isinstance(B, dict):
        return A or B
    return dict([(a, join(A.get(a), B.get(a))) for a in set(A.keys()) | set(B.keys())])

#Function for converting string to int
def convertInt(origString, loc, tokens):
   return int(tokens[0])

#Function for converting string to long
def convertLong(origString, loc, tokens):
   getcontext().prec = len(tokens[0]) - tokens[0].index(".")
   return long(tokens[0])

#Function for converting string to float
def convertFloat(origString, loc, tokens):
   getcontext().prec = len(tokens[0]) - tokens[0].index(".")
   #if representable as an int, do it
   if (int(float(tokens[0])) == float(tokens[0])):
      return int(Decimal(tokens[0]))
   else:
      return float(Decimal(tokens[0]))

#Function for converting string to complex
def convertComplex(origString, loc, tokens):
   return complex(tokens[0])
   
#Function for converting string to scientific notation
def convertSci(origString, loc, tokens):
   getcontext().prec = len(tokens[0]) - tokens[0].index(".")
   return getcontext().to_sci_string(Decimal(tokens[0]))
   
#Function for processing the document
def convertToDict(tokens):
   keys = []
   vals = []
   orig = tokens
   i = 0
   while i < (len(tokens)-1):
      #Assemble Prolog if found
      if str(tokens[i]).count("BEGIN_PROLOG") > 0:
         if keys.count("PROLOG") != 0:
            index = keys.index("PROLOG")
            vals[index] = join(vals[index], convertToDict(tokens[i][1:(str(tokens).rfind("END_PROLOG"))]))
         else:   
            keys.append("PROLOG")
            vals.append(convertToDict(tokens[i][1:(str(tokens).rfind("END_PROLOG"))]))
      #Else assemble doc body
      else:
         keys.append(tokens[i])
         #Found non-atom value
         if str(tokens[i + 1]) == ":":
            
            tokens.pop(i + 1)
            i += 1
            if len(tokens) > 1:
               #Found a table
               if str(tokens[i]).count(":") > 0 and str(tokens[i]).count("@") == 0:
                  vals.append(convertToDict(tokens[i]))
               #Found a sequence    
               elif str(tokens[i]).count("[") > 0:
                  vals.append(addBrackets(tokens[i]))
               #Found an atom
               else:
                  vals.append(tokens[i])
            else:
               raise INVALID_ASSOCIATION("Invalid Association @ " + str(orig) + "; Valid syntax => name : value")
         #Found an atom
         else:
            vals.append(tokens[i])
      i += 1
   return OrderedDict(zip(keys,vals))        

#Function for handling sequences
def addBrackets(tokens):
   return tokens.asList()

def checkAssoc(origString, loc, tokens):
   return tokens

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
        integer= Word(nums).setParseAction(convertInt)
        #float= MatchFirst(Word(nums, ".") | Word(nums, ".", nums)).setParseAction(convertFloat)
        float= Regex(r'[\d]*[.][\d*]').setParseAction(convertFloat)
        hex= Regex(r'0x[\da-fA-F]*')
        sci= Regex(r'[0-9\W]*\.[0-9\W]*[eE][0-9]*').setParseAction(convertSci)
        simple= float | integer
        complex= Combine("(" + simple - "," + simple + ")").setParseAction(convertComplex)
        number=  MatchFirst(sci | complex | simple | infinity | hex) 
        
        # --STRING--
        dot= Regex(r'[.]')
        uquoted= Word(alphas+'_', alphanums+'_')
        squoted = Regex(r'\'(?:\\\'|[^\'])*\'', re.MULTILINE)
        dquoted = Regex(r'\"(?:\\\"|[^"])*\"', re.MULTILINE)
        string= MatchFirst(dquoted | squoted | uquoted)
        begin= Literal("BEGIN_PROLOG")
        end= Literal("END_PROLOG")
        #name= uquoted & ~(begin | end)
        name= uquoted
        #Added "Combine" to recognize hname token
        hname= Combine(name + OneOrMore(dot - name))   
        id= MatchFirst(hname | name)

        # --MISC--
        ws= Regex(r'\s*').suppress()
        colon= ws + Regex(r':') + ws
        local= Regex(r'@local::')
        db= Regex(r'@db::')
        ref= Combine(local - id) | Combine(db - id)

        # --ATOM|VALUE--
        atom= MatchFirst(ref | number | string | null | bool).setResultsName("atom")
        #table & seq must be forwarded here so that a definition for value can be created
        table= Forward()
        seq= Forward()
        value= MatchFirst(atom | seq | table)

        # --ASSOCIATION-
        association= (id + colon - value).setResultsName("association")
        
        # --SEQUENCE--
        seq_item= value | Regex(r',').suppress()
        seq_body= nestedExpr('[', ']', seq_item) 
        #filling in forwarded definition
        seq << seq_body

        # --TABLE--
        table_item= association | Regex(r'\s')
        table_body= nestedExpr('{', '}', table_item)
        #filling in forwarded definition
        table<< table_body

        # --PROLOG--
        prolog= Group(begin + Optional(OneOrMore(table_item)) + end)
        prologs= OneOrMore(prolog)

        # --DOCUMENT--
        doc_body= Optional(OneOrMore(prolog)) - Optional(OneOrMore(table_item))
        document= doc_body
        return document
        #(Top)

#Is the passed line of input an include statement?
def isInclude(s):
        exists = s.count("#include") > 0
        if exists:
           BoL = s.index("#include") == 0
           if BoL:
              parens = s.count("\"") == 2
              if parens:
                 return True
              else:
                 return False
           else:
              return False
        else:
           return False

#Is the passed line of input a comment?
def isComment(s):
   if (s.count("#") > 0 or s.count(r'//') > 0) and not(isInclude(s)):
      if s.count("#") > 0:
         if s.index("#") == 0:
            return True
      elif s.count(r'//') > 0:
         if s.index(r'//') == 0:
            return True
   return False     

#Checks to see if the passed string is an hname
def isHName(s):
        return str(s).count(".") > 0

#Checks to see if a document (string) is considered "empty"
#A document is considered "empty" if it contains only comments or only (a) prolog(s).
def isEmptyDoc(s):
        content = s.splitlines(0)
        if len(content) == 0:
           return False
        for line in content:
           if (not(isComment(line)) and isInclude(line)) or line != "":
              return False
        return True

#Reads External file and returns the contents
def handleInclude(s):
        #try:
           name = s.split('"')
           name = name[1]
           try:
              file = open(name)
              fileContents = file.read()
              return fileContents
           except IOError as e:
              print("({0})".format(e))
        #except IndexError as e:
        #   raise INVALID_INCLUDE_SYNTAX("Incorrect syntax for #include: " + name[0] + ". Valid syntax: #include \"filename.ext\"")
              
#Function to handle includes before grammar parsing begins      
def checkIncludes(s):
        #insertLater = []
        content = s.splitlines(0)
        pcontent = str("")
        i = 0
        while i < len(content):
           try:
              #Checking for illegal statements before PROLOG
              #Comments are allowed
              if not(isComment(content[i])) and content.count("BEGIN_PROLOG") > 0:
                 j = content.index("BEGIN_PROLOG")
                 if j > i:
                    raise ILLEGAL_STATEMENT(content[i])
              #Is the line an include?
          
              if isInclude(content[i]):
                 fileContents = handleInclude(content[i])
                 if fileContents != None:
                    if fileContents.count("#include") > 0:
                       fileContents = handleInclude(fileContents)
                    pcontent += fileContents
              #Otherwise just add it to the parsed content
              else:
                 pcontent += content[i]
                 pcontent += "\n"
           except IOError as e:
              #print ("({0})".format(e))
              raise
           except ILLEGAL_STATEMENT as e:
              #print ("({0})".format(e))
              raise
           else:
              i += 1
        #return the parsed content
        return pcontent

#recursive handling of overrides
def recOverride(dic, key, val):
   #Look for a DOT_INDEX token
   if key.count(".") > 0:
      #split off the leading name
      newKey = key.split(".", 1)
      #descend one level in the dictionary
      #and continue checking the rest of the hname
      return recAssoc(dic[newKey[0]], newKey[1])
   else:
      if key in dic:
         dic[key] = val
         return dic
      else:
         raise INVALID_KEY("Key " + key + " does not exist in parameter set.")

#function for handling Left-Hand side Hnames
def handleOverride(dic, k):
   if isHName(k):
      key = k.split(".", 1)
      if key[0] in dic:
         dic[key[0]] = recOverride(dic[key[0]], key[1], dic[k])
         delItems.append(k)
      else:
         raise INVALID_KEY("Key " + key[0] + " does not exist in parameter set.")
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

def handleRef(dic, key, val):
        newKey = val.split("::")        
        newKey = newKey[1]
        # VERSION 4: Line By Line
        if isHName(newKey):
           #Break off the first "chunk" (top-level name):
           newKey = newKey.split(".", 1)
           #Is the top-level name in the PROLOG?
           if "PROLOG" in dic and newKey[0] in dic["PROLOG"]:
              return recRef(dic["PROLOG"][newKey[0]], newKey[1])
           #Otherwise:
           else:
              return recRef(dic[newKey[0]], newKey[1])
        # Otherwise:
        else:
           # Is the key in the PROLOG?:
           if "PROLOG" in dic and newKey[0] in dic["PROLOG"]:
              return dic["PROLOG"][newKey]
           # Otherwise:
           else:
              return dic[newKey]
        return dic

def postParse(dic):
   for k,v in dic.iteritems():
      #Conversion from OrderedDict back to standard dictionary
      if type(v) is OrderedDict:
         dic[k] = dict(postParse(v))
      if k == "PROLOG":
         dic[k] = postParse(dic[k])
      #Found an hname
      if isHName(k):
         dic = handleOverride(dic, k)
      #Found a reference
      if str(v).count("::") > 0:
         dic[k] = handleRef(dic, k, v)
   # Deleting resolved overrides from dictionary
   for item in delItems:
      del dic[item]
   return dic

def orderCheck(s):
   content = s.splitlines();
   i = 0
   while i < len(content) - 1: 
      if not(isComment(content[i])) and content.count("BEGIN_PROLOG") > 0:
         j = content.index("BEGIN_PROLOG")
         if j > i:
            raise ILLEGAL_STATEMENT(content[i], i)
      i += 1
   return True

def parse(s):
        try:
           doc = Syntax()
           #ignoring comments
           doc.ignore(ccomment)
           doc.ignore(pcomment)

           content = str("")
           #check for empty doc/only comments
           if isEmptyDoc(s):
              #If the document is empty, or just has comments/empty lines
              #Return an empty dictionary
              return dict()
	   if orderCheck(s):	
              #includes checking
              if s.count("#include") > 0:
                 s = checkIncludes(s)
              #parse contents of file
              docStr = doc.parseString(s)
              #convert over to proper dictionary
              docStr = convertToDict(docStr)  
              #resolving references and hnames
              docStr = postParse(docStr)

           #removing PROLOG (no longer needed)
           if "PROLOG" in docStr:
              del docStr["PROLOG"]
           if "END_PROLOG" in docStr:
              del docStr["END_PROLOG"]
           return dict(docStr)
        except IOError as e:
           print ("IOError: " + "({0})".format(e))
        except ILLEGAL_STATEMENT as e:
           print ("ILLEGAL_STATEMENT: " + "({0})".format(e))
        except INVALID_INCLUDE_SYNTAX as e:
           print ("INVALID_INCLUDE_SYNTAX: " + "({0})".format(e))
        except INVALID_ASSOCIATION as e:
           print ("INVALID_ASSOCIATION: " + "({0})".format(e))
        except ParseBaseException as e:
           print ("Parse Exception: " + "({0})".format(e))
if __name__ == '__main__':
        contents = sys.stdin.read()
        d= parse(contents)
        print d
