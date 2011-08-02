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
class INVALID_TOKEN(Exception):
   def __init__(self, stmt):
      self.msg = "Invalid token detected, resulting in an empty parameter set: " + stmt
   def __str__(self):
      return repr(self.msg)

class INVALID_KEY(Exception):
   def __init__(self, stmt):
      self.msg = stmt
   def __str__(self):
      return repr(self.msg)

class INVALID_INCLUDE(Exception):
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
   
#Function for handling sequences
def addBrackets(tokens):
   return tokens.asList()

def checkAssoc(origString, loc, tokens):
   return tokens

#Allows combined grammar to ignore commented lines
comment= oneOf('# //') + ZeroOrMore(Word(r'*')) + LineEnd()
pcomment= Regex(r'\#.*') + LineEnd()
ccomment= Regex(r'//.*') + LineEnd()

#Rest of Grammar
def Syntax():
   #(Bottom)
   # --BOOLEAN--
   true= Word("True")
   false= Word("False")
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
   number=  NoMatch().setName("number") | MatchFirst(sci | complex | simple | infinity | hex)
        
   # --STRING--
   uquoted= Word(alphas+'_', alphanums+'_')
   squoted = Regex(r'\'(?:\\\'|[^\'])*\'', re.MULTILINE)
   dquoted = Regex(r'\"(?:\\\"|[^"])*\"', re.MULTILINE)
   string= MatchFirst(dquoted | squoted | uquoted)
   name= NoMatch().setName("name") | uquoted
   dot= Regex(r'[.]') + name
   bracket= Regex(r'\[[\d]\]')
   #Added "Combine" to recognize hname token
   hname= NoMatch().setName("hname") | Combine(name + (bracket|dot) + ZeroOrMore(bracket|dot))
   id= MatchFirst(hname | name).setName("ID")

   # --MISC--
   ws= Regex(r'\s*').suppress()
   colon= NoMatch().setName("colon") | (ws + ':' + ws)
   local= Regex(r'@local::')
   db= Regex(r'@db::')
   ref= NoMatch().setName("reference") | (Combine(local - id) | Combine(db - id))

   # --ATOM|VALUE--
   atom= NoMatch().setName("atom") | MatchFirst(ref | number | string | null | bool).setName("atom")
   #table & seq must be forwarded here so that a definition for value can be created
   table= Forward()
   seq= Forward()
   value= NoMatch().setName("value") | MatchFirst(atom | seq | table).setName("value")

   # --ASSOCIATION-
   association= (id - colon - value)
        
   # --SEQUENCE--
   seq_item= NoMatch().setName("seq_item") | MatchFirst(value | Regex(r',').suppress())
   seq_body= nestedExpr('[', ']', seq_item) 
   #filling in forwarded definition
   seq << seq_body

   # --TABLE--
   table_item= NoMatch().setName("table_item") | MatchFirst(association | Regex(r'\s'))
   table_body= nestedExpr('{', '}', table_item)
   #filling in forwarded definition
   table<< table_body

   # --DOCUMENT--
   doc_body= ZeroOrMore(table_item)
   document= doc_body
   return document
   #(Top)

def Prolog():
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
   name= uquoted
   #Added "Combine" to recognize hname token
   hname= Combine(name + OneOrMore(dot - name))
   id= MatchFirst(hname | name)

   # --MISC--
   ws= Regex(r'\s*').suppress()
   colon= ws + ':' + ws
   local= Regex(r'@local::')
   db= Regex(r'@db::')
   ref= Combine(local - id) | Combine(db - id)

   # --ATOM|VALUE--
   atom= MatchFirst(ref | number | string | null | bool).setResultsName("atom")
   #table & seq must be forwarded here so that a definition for value can be created
   table= Forward()
   seq= Forward()
   value= MatchFirst(atom | seq | table)

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
   prolog= begin + Optional(OneOrMore(table_item)) + end
   prologs= OneOrMore(prolog)
   return prologs

#Is the passed line of input an include statement?
def isInclude(s):
        exists = s.count("#include") > 0
        if exists:
           BoL = s.index("#include") == 0
           if BoL:
              space = False
              if s.count(" ") > 0:
                 space = s.index(" ") == 8
              quotes = s.count("\"") == 2
              if quotes and space:
                 return True
              else:
                 raise INVALID_INCLUDE("Syntax error at : " + s)
                 #return False
           else:
              return False
        else:
           return False

#Is the passed line of input a comment?
def isComment(s):
   if not(isInclude(s)):
      if (s.count("#") > 0 or s.count(r'//') > 0):
         if s.count("#") > 0:
            if s.index("#") == 0:
               return True
            else:
               return False
         elif s.count(r'//') > 0:
            if s.index(r'//') == 0:
               return True
            else:
               return False
      else:
         return False
   else:
      return False     

def isRef(s):
   return str(s).count("::") > 0

#Checks to see if the passed string is an hname
def isHName(s):
        return (str(s).count(".") > 0 or str(s).count("[") > 0)

#Checks to see if a document (string) is considered "empty"
#A document is considered "empty" if it contains only comments or only (a) prolog(s).
def isEmptyDoc(s):
        content = s.splitlines(1)
        #if there's nothing in s
        if len(content) == 0:
           return True
        else:
           for line in content:
              #broken!
              if (not(isComment(line)) and line != "" and line != "\n"):
                 return False
        return True

#Reads External file and returns the contents
def handleInclude(s):
   name = s.split('"')
   name = name[1]
   file = open(name)
   fileContents = file.read()
   return fileContents
              
#Function to handle includes before grammar parsing begins      
def checkIncludes(s):
        content = s.splitlines(1)
        pcontent = str("")
        i = 0
        while i < len(content):
           #Is the line an include?
           if isInclude(content[i]):
              fileContents = handleInclude(content[i])
              if fileContents != None:
                 if fileContents.count("#include") > 0:
                    fileContents = handleInclude(fileContents)
                 pcontent += fileContents
           #Otherwise just add it to the parsed content
           else:
              #raise INVALID_INCLUDE("Syntax error on line " + str(i))
              pcontent += content[i]
           i += 1
        #return the parsed content
        return pcontent

def detIndType(s):
   b = s.find("[")
   d = s.find(".")
   if b == -1 and d > -1:
      return "."
   if d == -1 and b > -1:
      return "["
   if b == -1 and d == -1:
      return ""
   elif ( d <= b):
      return "."
   elif ( b <= d):
      return "["

def stripCloseB(s):
   s = s.split("]", 1)
   s = s[0] + s[1]
   return s

def handleRHname(s, d):
   indexChar = detIndType(s)
   if indexChar != "":
      if indexChar == "[":
         s = s.stripCloseB(s)
      s = s.split(indexChar, 1)
      key = s[0]
      rest = s[1]
      if key in d:
         return handleRHname(rest, d[key])
      else:
         raise KeyError(key)
   elif s in d:
      return d[s]
   else:
      raise KeyError(key)

def handleLHname(s, d, v):
   indexChar = detIndType(s)
   if indexChar != "":
      if indexChar == "[":
         s = stripCloseB(s)
      s = s.split(indexChar, 1)
      key = s[0]
      rest = s[1]
      return handleRHname(rest, d[key])
   else:
      if type(d) is list:
         index = int(s)
         if index > (len(d) - 1):
            d.append(v)
         else:
            d[int(s)] = v
      else:
         d[s] = v
      return d

def postParse(d, p):
   for k, v in d.iteritems():
      if type(v) is OrderedDict:
         d[k] = postParse(dict(v), p)
      if isRef(v):
         key = v.split("::")[1]
         indChar = detIndType(key)
         if indChar != "":
            if indChar == "[":
               key = stripCloseB(key)
            testKey = key.split(indChar, 1)[0]
            if testKey in d:
               d[k] = handleRHname(key, d)
            elif testKey in p:
               d[k] = handleRHname(key, p)
            else:
               raise KeyError("In postParse: " + k)
         elif key in d:
            d[k] = d[key]
         elif key in p:
            d[k] = p[key]
      if isHName(k):
         splitChar = detIndType(k)
         newKey = k
         if splitChar != "":
            if splitChar == "[":
               newKey = stripCloseB(k)
            newKey = newKey.split(splitChar, 1)
            rest = newKey[1]
            newKey = newKey[0]
            if newKey in d:
               d[newKey] = handleLHname(rest, d[newKey], v)
            elif newKey in p:
               #Raise error?
               p[newKey] = handleLHname(rest, d[newKey], v)
         del d[k]
   return d
            #else:
            #   raise KeyError(testKey)

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

#Function for processing the document
def convertToDict(tokens):
   keys = []
   vals = []
   orig = tokens
   i = 0
   while i < (len(tokens)-1):
      keys.append(tokens[i])
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

def assembleProlog(tokens):
   keys = []
   vals = [] 
   i = 0
   while i < (len(tokens)-1):
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
   dict = OrderedDict(zip(keys,vals))
   del dict["BEGIN_PROLOG"]
   #del dict["END_PROLOG"]
   return dict

def parse(s):
        try:
           prologs = []
           doc = Syntax()
           pro = Prolog()

           #ignoring comments
           doc.ignore(ccomment)
           doc.ignore(pcomment)
           #doc.ignore(comment)
           pro.ignore(ccomment)
           pro.ignore(pcomment)

           content = str("")
           isEmpty = False
           #check for empty doc/only comments
           if isEmptyDoc(s):
              #If the document is empty, or just has comments/empty lines
              #Return an empty dictionary
              return dict()
           elif orderCheck(s):  
              #includes checking
              if s.count("#include") > 0:
                 s = checkIncludes(s)
              #handle prolog(s)
              if s.count("BEGIN_PROLOG") > 0:
                 prologStr = s[:s.rfind("END_PROLOG")+10]
                 s = s[s.rfind("END_PROLOG")+10:len(s)]
                 prologs = pro.parseString(prologStr)
                 prologs = assembleProlog(prologs)
              #parse contents of file
              docStr = doc.parseString(s)
              #convert over to proper dictionary
              docStr = convertToDict(docStr)  
              #resolving references and hnames
              docStr = postParse(docStr, prologs)
              #docStr = docStr
              if docStr == {} and not(isEmptyDoc(s)):
                 raise INVALID_TOKEN(str(docStr))
              else:
                 return dict(docStr)
           else:
              raise ILLEGAL_STATEMENT(str(docStr))
        except KeyError as e:
           print ("KEY_ERROR: " + "({0})".format(e))
        except INVALID_TOKEN as e:
           print ("INVALID_TOKEN: " + "({0})".format(e))
        except IOError as e:
           print ("IO_ERROR: " + "({0})".format(e))
        except ILLEGAL_STATEMENT as e:
           print ("ILLEGAL_STATEMENT: " + "({0})".format(e))
        except INVALID_INCLUDE as e:
           print ("INVALID_INCLUDE: " + "({0})".format(e))
        except INVALID_ASSOCIATION as e:
           print ("INVALID_ASSOCIATION: " + "({0})".format(e))
        except ParseBaseException as e:
           #if e.msg.count("@local::") > 0:
           #   e.msg = "Expected a value"
           print ("PARSE_EXCEPTION: " + "({0})".format(e))
if __name__ == '__main__':
        contents = sys.stdin.read()
        d= parse(contents)
        print d
