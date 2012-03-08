#==========FHICLPY=============================================================
# AUTHOR: Ryan Putz
# This is a python-based parser which utilizes 
# the PyParsing module by Paul McGuire.
# It is a top-down, recursive descent parser.
#
# IMPLEMENTATION DIFFERENCES:
#    This version of fhicl-py allows for the overriding of 
#    prolog entries by non-prolog entries
#    of the same name. This change is in accordance with 
#    git commit #69b72b863987c8b52ca781f1823c2c447b887ccf
#    of fhicl-cpp wherein a similar modification was made.
# 
# CURRENT ISSUES: ?
#==============================================================================
import sys, string, re, decimal, ast
import os.path
import pyparsing as pp


from orderedDict import OrderedDict
from decimal import *

#========================================================
#                 CUSTOM EXCEPTIONS
#========================================================
class INVALID_TOKEN(Exception):
   def __init__(self, stmt):
      self.msg = "Invalid token detected! " + stmt
   def __str__(self):
      return repr(self.msg)

class INVALID_KEY(Exception):
   def __init__(self, stmt):
      self.msg = stmt
   def __str__(self):
      return repr(self.msg)

class INVALID_INCLUDE(Exception):
   def __init__(self, stmt):
      self.msg = "Invalid #include statement detected! " + stmt
   def __str__(self):
      return repr(self.msg)

class PARSE_FAILURE(pp.ParseSyntaxException):
   def __init__(self, stmt):
      self.msg = stmt
   def __str__(self):
      return repr(self.msg)

class ILLEGAL_STATEMENT(Exception):
   def __init__(self, stmt, i):
      self.msg = ("Illegal statement found before PROLOG at line " 
         + str(i) + " => " + stmt)
   def __str__(self):
      return repr(self.msg)

class INVALID_ASSOCIATION(Exception):
   def __init__(self, stmt):
      self.msg = "Invalid syntax for an association! " + stmt
   def __str__(self):
      return repr(self.msg)

#========================================================
#           PARSE BEHAVIOR FUNCTIONS/METHODS
#========================================================

#==============================================================================
#joining two dictionaries (recursive)
#==============================================================================
def join(A, B):
    if not isinstance(A, dict) or not isinstance(B, dict):
        return A or B
    return dict([(a, join(A.get(a), B.get(a))) for a in set(A.keys()) | set(B.keys())])

#==============================================================================
#Function for converting string to int
#==============================================================================
def convertInt(origString, loc, tokens):
   return int(tokens[0])

#==============================================================================
#Function for converting string to long
#==============================================================================
def convertLong(origString, loc, tokens):
   getcontext().prec = len(tokens[0]) - tokens[0].index(".")
   return long(tokens[0])

#==============================================================================
#Function for converting string to float
#==============================================================================
def convertFloat(origString, loc, tokens):
   getcontext().prec = len(tokens[0]) - tokens[0].index(".")
   #if representable as an int, do it
   if (int(float(tokens[0])) == float(tokens[0])):
      return int(Decimal(tokens[0]))
   else:
      return float(Decimal(tokens[0]))

#==============================================================================
#Function for converting string to complex
#==============================================================================
def convertComplex(tokens):
   cmplx = ast.literal_eval(tokens[0])
   return cmplx
   
#==============================================================================
#Function for converting string to scientific notation
#==============================================================================
def convertSci(origString, loc, tokens):
   getcontext().prec = len(tokens[0]) - tokens[0].index(".")
   number = str(float(Decimal(tokens[0])))
   number = re.sub(r'([Ee])\+',r'\1',number)
   if int(Decimal(number)) == float(number): 
      number = str(int(Decimal(number)))
   return '%s' % (number,)
   
#==============================================================================
#Function for converting string to hexadecimal 
#==============================================================================
def convertHex(origString, loc, tokens):
   #return int(tokens[0], 16)
   return tokens[0]

#==============================================================================
#Function for converting to a list
#==============================================================================
def convertList(tokens):
   return tokens.asList()

#==============================================================================
#checks the passed string for malformed, unquoted strings.
#==============================================================================
def checkStr(origString, loc, tokens):
   strg = origString[origString.index(tokens[0]) + len(tokens[0]):len(origString)]
   strg = strg.replace("\n", "")
   if strg.count(":") == 0 and strg.count("::") == 0 and strg.count(".") == 0 and strg.count("[") == 0 and strg != "":
      if tokens[0] in strg or tokens != strg:
         raise INVALID_TOKEN("Invalid Token @ " + strg)
   elif str(tokens[0])[0].isdigit():
         raise INVALID_TOKEN("Invalid Token @ " + tokens[0])
   return tokens

#==============================================================================
#Raises an INVALID_TOKEN exception
#==============================================================================
def raiseInvalidToken(origString, loc, tokens):
   raise INVALID_TOKEN("Invalid Token @ " + tokens)

#hname storage:
#Items in this list are left-hand heirarchical names
#that are to be removed from the parameter set after
#being resolved
delItems = []
#========================================================
#                       GRAMMAR
#========================================================
# Leading "NoMatch()" elements indicate what to do if the 
# parser can't match a token once it has committed to a type

#Comments:
#Allows combined grammar to ignore commented lines
comment= pp.oneOf('# //') + pp.ZeroOrMore(pp.Word(r'*')) + pp.LineEnd()
pcomment= pp.Regex(r'\#.*') + pp.LineEnd()
ccomment= pp.Regex(r'//.*') + pp.LineEnd()

#Parameter Set Grammar:
def Syntax():

   #(Bottom)
   # --BOOLEAN--
   true= pp.Word("True")
   false= pp.Word("False")
   bool= true | false

   # --MISC--
   ws= pp.Regex(r'\s*').suppress()
   lparen= pp.Literal("(").suppress()
   rparen= pp.Literal(")").suppress()
   colon= pp.NoMatch().setName("colon") | (ws + ':' + ws)
   local= pp.Regex(r'@local::')
   db= pp.Regex(r'@db::')

   # --NUMBER--
   null= pp.Word('nil')
   infinity= pp.oneOf( 'infinity' '+infinity' '-infinity')
   integer= pp.Word(pp.nums).setParseAction(convertInt)
   float= pp.Regex(r'[\d]*[.][\d*]').setParseAction(convertFloat)
   hex= pp.Regex(r'(0x|$|0X)[0-9a-fA-F]+').setParseAction(convertHex)
   bin= pp.Regex(r'(0b)[01]+')
   sci= pp.Regex(r'[0-9\W]*\.[0-9\W]*[eE][0-9]*').setParseAction(convertSci)
   simple= float | integer
   complex= pp.Combine(lparen + ws + simple + ws + "," + ws + simple + ws + rparen).setParseAction(convertComplex)
   number=  pp.NoMatch().setName("number") | pp.MatchFirst(sci | complex | hex | simple | infinity)
        
   # --STRING--
   uquoted= pp.NoMatch().setName("unquoted string") | pp.Word(pp.alphanums+'_').setParseAction(checkStr)
   squoted = pp.Regex(r'\'(?:\\\'|[^\'])*\'', re.MULTILINE)
   dquoted = pp.Regex(r'\"(?:\\\"|[^"])*\"', re.MULTILINE)
   string= pp.NoMatch().setName("string") | pp.MatchFirst(dquoted | squoted | uquoted)
   #name= pp.NoMatch().setName("name") | pp.Word(pp.alphas+'_', pp.alphanums+'_')
   name= pp.NoMatch().setName("name") | uquoted
   dot= pp.Regex(r'[.]') + name
   bracket= pp.Regex(r'\[[\d]\]')
   #Added "Combine" to recognize hname token
   hname= pp.NoMatch().setName("hname") | pp.Combine(name + (bracket|dot) + pp.ZeroOrMore(bracket|dot))
   id= pp.NoMatch().setName("name or hname") | pp.MatchFirst(hname | name).setName("ID")
   ref= pp.NoMatch().setName("reference") | (pp.Combine(local - id) | pp.Combine(db - id))

   # --ATOM|VALUE--
   atom= pp.NoMatch().setName("atom") | pp.MatchFirst(ref | number | string | null | bool).setName("atom")
   #table & seq must be forwarded here so that a definition for value can be created
   table= pp.Forward()
   seq= pp.Forward()
   value= pp.NoMatch().setName("value") | pp.MatchFirst(atom | seq | table).setName("value")

   # --ASSOCIATION-
   association= pp.NoMatch().setName("association") | (id - colon - value)
        
   # --SEQUENCE--
   seq_item= pp.NoMatch().setName("seq_item") | pp.MatchFirst(value | pp.Regex(r',').suppress())
   seq_body= pp.nestedExpr('[', ']', seq_item) 
   #filling in forwarded definition
   seq << seq_body

   # --TABLE--
   table_item= pp.NoMatch().setName("association") | pp.MatchFirst(association | pp.Regex(r'\s'))
   table_body= pp.nestedExpr('{', '}', table_item)
   #filling in forwarded definition
   table<< table_body

   # --DOCUMENT--
   doc_body= pp.NoMatch().setName("association") | pp.ZeroOrMore(table_item)
   document= doc_body
   return document
   #(Top)

#========================================================
#                      END GRAMMAR
#========================================================

#========================================================
#                      FUNCTIONS/METHODS
#========================================================

#==============================================================================
#isInclude(s)
#Is the passed string an include statement?
#Checks for presence of "#include" as well as location on a line
#PARAMS: a string to be checked
#==============================================================================
def isInclude(s):
        exists = s.count("#include") > 0
        if exists:
           BoL = s.index("#include") == 0
           if BoL:
              space = (s.count(" ") >= 1 and s.index(" ") == 8)
              if space:
                 return True
              else:
                 raise INVALID_INCLUDE(s + " is not a valid include statement.")
           else:
              return False
        else:
           return False

#==============================================================================
#isComment(s)
#Is the passed string a comment?
#Checks for both "#" and "//" notations as well as location on a line
#PARAMS: a string to be checked
#==============================================================================
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

#==============================================================================
#isRef(s)
#Is the passed string a reference?
#PARAMS: a string to check
#==============================================================================
def isRef(s):
   return str(s).count("::") > 0 and str(s).count("@") > 0

#==============================================================================
#isHName(s)
#Is the passed string an hname?
#PARAMS: a string to check
#==============================================================================
def isHName(s):
        return (str(s).count(".") > 0 or (str(s).count("[") > 0 and str(s).count("[") == str(s).count("]")))

#==============================================================================
#isEmptyDoc(s)
#Checks to see if a document (string) is considered "empty"
#A document is considered "empty" if it contains only comments or only (a) prolog(s).
#PARAMS: a string (possibly empty) to check.
#==============================================================================
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

#==============================================================================
#isString(s)
#Function which looks for matching pairs of single or double quotes
#PARAMS: a character sequence to be checked.
#==============================================================================
def isString(s):
   s = str(s)
   if s.count("'") == 2:
      if s.find("'") == 0 and s.rfind("'") == len(s) - 1:
         return True
   elif s.count('"') == 2:
      if s.find('"') == 0 and s.rfind('"') == len(s) - 1:
         return True
   else:
      return False

#==============================================================================
#handleInclude(s)
#Reads External file and returns the contents
#PARAMS: the #include statement to process.
#==============================================================================
def handleInclude(s):
   name = s.split('"')
   try:
      name = name[1]
      file = open(name)
      fileContents = file.read()
      return fileContents
   except:
      raise INVALID_INCLUDE(s + " is not a valid include statement.")
              
#==============================================================================
#checkIncludes(s)
#Function to handle includes before grammar parsing begins.
#PARAMS: A string containing #include statements to be validated and processed
#==============================================================================
def checkIncludes(s):
        content = s.splitlines(1)
        pcontent = str("")
        i = 0
        while i < len(content):
           #Is the line an include?
           if isInclude(content[i]):
              fileContents = checkIncludes(handleInclude(content[i]))
              if fileContents != None:
                 pcontent += fileContents
           #Otherwise just add it to the parsed content
           else:
              pcontent += content[i]
           i += 1
        #return the parsed content
        return pcontent

#==============================================================================
#detIndType(s)
#Function that determines which type of indexing is being used in an hname.
#The two options are DOT(".") index or BRACKET("[]") index.
#The decision is made based on existence and location within a string
#PARAMS: a string containing either a FHiCL name or hname.
#==============================================================================
def detIndType(s):
   s = str(s)
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

#==============================================================================
#stripCloseB(s)
#Utility function for stripping off the closing bracket in bracket notation
#PARAMS: A string containing "]"
#==============================================================================
def stripCloseB(s):
   s = str(s).split("]", 1)
   s = s[0] + s[1]
   return s

#==============================================================================
#handleRHname(s, d)
#Function that handles look-up of hname references
#PARAMS: the hname, the dictionary to search in
#==============================================================================
def handleRHname(s, d):
   indexChar = detIndType(s)
   if indexChar != "":
      if indexChar == "[":
         s = stripCloseB(s)
      s = s.split(indexChar, 1)
      key = s[0]
      rest = s[1]
      if type(d) is list and len(d)-1 > int(key):
         return handleRHname(rest, d[int(key)])
      elif key in d:
         return handleRHname(rest, d[key])
      else:
         raise KeyError(key + " not in " + str(d))
   elif s in d:
      return d[s]
   else:
      raise KeyError(s + " not in " + str(d))

#==============================================================================
#handleLHname(s, d, v)
#Function that handles overrides using hnames
#PARAMS: the string containing the "address" of the referenced value,
#       the dictionary to search in, and the value to replace. 
#==============================================================================
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
         return d
      else:
         return dict(zip(list(s), list(str(v))))

#==============================================================================
#resolveRef(d, p, v)
#This function performs a lookup of the referenced value and returns it.
#PARAMS: The primary dictionary to search in, the prolog dictionary, 
#        the hname to lookup (resulting in a value)
#==============================================================================
def resolveRef(d, p, v):
   #Found a reference
   if isRef(v):
      key = v.split("::")[1]
      indChar = detIndType(key)
      #if it's an HName
      if indChar != "":
         #If it's a brace index, strip off the closing brace
         if indChar == "[":
            key = stripCloseB(key)
         #split at the indexing character
         testKey = key.split(indChar, 1)[0]
         #check to see if the leading name is in the document dictionary
         if testKey in d:
            #if so, recursively handle the hname
            v = handleRHname(key, d)
         #else check to see if the key is in the prolog dictionary
         elif testKey in p:
            #if so, recursively handle the hname
            v = handleRHname(key, p)
         else:
            #Otherwise, error out
            raise KeyError(testKey + " not in " + d)
      #If it's not an hname
      #check to see if the name exists in d
      elif key in d:
         v = d[key]
      #else check to see if the name exists in p
      elif key in p:
         v = p[key]
      else:
         raise KeyError(key + " not in " + d)
   return v

#==============================================================================
#resolveHName(d, p, k, v)
#This function performs the lookup of a FHiCL hname, and makes the appropriate
#change to the value associated with the referenced key.
#PARAMS: The primary dictionary to look in, the prolog dictionary,
#        the full hname (key), and the value to substitute in.
#==============================================================================
def resolveHName(d, p, k, v):
   #If it's an hname
   if isHName(k):
      #determine which type of indexing is being used next
      newKey = k
      splitChar = detIndType(k)
      #If there is a type of index being used 
      if splitChar != "":
         #If it's bracket indexing, strip off the closing bracket
         if splitChar == "[":
            newKey = stripCloseB(k)
         #Split on the splitChar
         newKey = newKey.split(splitChar, 1)
         #Two pieces: chunk before split char => newKey
         #            chunk after split char => rest
         rest = newKey[1]
         newKey = newKey[0]
         #If the newKey is in the PSet
         if newKey in d:
            #Handle hname override
            d[newKey] = handleLHname(rest, d[newKey], v)
         #Else if newKey is in the Prolog
         elif newKey in p:
            #Handle hname override 
            d[newKey] = handleLHname(rest, p[newKey], v)
         delItems.append(k)
   return d

#==============================================================================
#orderCheck(s)
#Function that checks the input string for illegal statements before prologs
#PARAMS: A string containing the contents of a FHiCL file to be checked.
#==============================================================================
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

#==============================================================================
#checkKey(k)
#Function to validate names (I.E. can only start with an underscore or alpha character)
#NOTE: This function can be modified to include other checks, as well.
#PARAMS: a key to validate
#==============================================================================
def checkKey (k):
   if k[0].isdigit() and (k[0].isalpha() or k[0] == "_"):
      raise INVALID_TOKEN(k)

#==============================================================================
#buildPSet(toks, p={})
#Construction of a parameter set. Used for both the prolog and document body
#PARAMS: list of parse results (I.E. tokens), optional prolog parameter set
#==============================================================================
def buildPSet(toks, p={}):
   #Empty Dictionary
   newDict = {}
   key = ""
   val = ""
   #Step through the parse tree (toks)
   while len(toks) > 0:
      #Checks to ensure that there are tokens to process and that each line is 
      #a valid association
      if len(toks) > 1 and str(toks[1]) == (":"):
         key = toks.pop(0)
         #Is it a valid fhicl name?
         checkKey(key)
         toks.pop(0) #dumping the ":"
         #Still have tokens left?
         if len(toks) > 0:
            #If it's not a quoted string
            if not isString(toks[0]):
               #Reference checking/handling
               if (str(toks[0]).count("@") > 0 
                  and str(toks[0]).index("@") == 0):
                  val = toks.pop(0)
               #Sequence/Table checking/handling
               elif (str(toks[0]).count("[") > 0 
                  and str(toks[0]).count("[") == str(toks[0]).count("]")):
                  #In the parse tree of tokens, fhicl sequences and tables are 
                  #both denoted by brackets ("[]"). Tables, however, contain 
                  #associations, so we can make a distinction based on if the 
                  #body contains (":"). These 4 lines of code handle the case of
                  #"I have a sequence of tables" 
                  #I.E. seq:[ { a:1 b:2 }, { c:3 d:4 } ]
                  #Wherein the parse tree treats everything as lists of tokens 
                  #until we assemble them here. So we can't just blindly check 
                  #for (":"), and we have to ensure that we're not calling it a
                  #table.
                  #if it's really a sequence of tables:
                  secBrack = -1
                  if str(toks[0]).count("[") > 1:
                     strg = str(toks[0]).split("[", 1)[1]
                     secBrack = strg.index("[")
                  #Table
                  if (str(toks[0]).count(":") > 0 
                     and (secBrack == -1 or str(toks[0]).index(":") < secBrack)):
                     val = buildPSet(toks.pop(0), p)
                  else:
                     #Manually assemble list, checking to see if each element 
                     #is a non-table value or a table body
                     val = []
                     for item in toks[0]:
                        if str(item).count(":") > 0:
                           val.append(buildPSet(item))
                        else:
                           val.append(item)
                     #done with that token, trash it.
                     toks.pop(0) 
               #Otherwise we have an unquoted string/numeric
               else:
                  val = toks.pop(0)
            #Otherwise it's a quoted string
            else:
               val = toks.pop(0)
               #Strip off the single or double quotes
               val = val[1:len(val)-1]
         #Otherwise the association is malformed
         else:
            raise INVALID_ASSOCIATION("Invalid Association @ " + str(toks) 
               + "; Valid syntax => name : value")
      #Otherwise it's a BEGIN/END token
      else:
         val = toks.pop(0)
      val = resolveRef(newDict, p, val) 
      newDict = resolveHName(newDict, p, key, val)
      newDict[key] = val
   #removing resolved overrides
   for item in delItems:
      del newDict[item]
      delItems.pop(0)
   return newDict

#==============================================================================
#assemblePrologStr(s)
#Assembles a prolog string by stripping out START and END tokens.
#PARAMS: a string containing a FHiCL prolog
#==============================================================================
def assemblePrologStr(s):
   prologStr = s.split("BEGIN_PROLOG")
   newStr = ""
   for item in prologStr:
      newStr += item.strip() + "\n"
   newStr = newStr.split("END_PROLOG")
   newStr2 = ""
   for item in newStr:
      newStr2 += item.strip() + "\n"
   return newStr2

#==============================================================================
#parse(s)
#Order of Processesing:
# 1. Checks for an empty document
# 2. Checks for invalid statements before prolog
# 3. Validates and imports #include statements
# 4. Processes and builds prolog parameter set
# 5. Processes and builds document parameter set
#PARAMS: a string containing the contents of a FHiCL file
#==============================================================================
def parse(s):
        try:
           prologs = []
           doc = Syntax()

           #ignoring comments
           doc.ignore(ccomment)
           doc.ignore(pcomment)
           
           content = str("")
           isEmpty = False
           #check for empty doc/only comments
           if isEmptyDoc(s):
              #If the document is empty, or just has comments/empty lines
              #Return an empty dictionary
              return dict()
           elif orderCheck(s):  
              #resolving include statements
              if s.count("#include") > 0:
                 s = checkIncludes(s)
              #handle prolog(s)
              if s.count("BEGIN_PROLOG") > 0:
                 prologStr = s[s.find("BEGIN_PROLOG")+12:s.rfind("END_PROLOG")-1]
                 s = s[s.rfind("END_PROLOG")+10:len(s)]
                 prologStr = assemblePrologStr(prologStr)
                 prologs = doc.parseString(prologStr)
                 prologs = buildPSet(prologs)
              #parse contents of file
              docStr = doc.parseString(s)
              numAssocs = docStr.asList().count(":") - docStr.asList().count("::")
              #convert over to proper dictionary
              docStr = buildPSet(docStr, prologs)
              docStr = dict(docStr)
              #Covers the case of a malformed name in a single association,
              #which makes up the entire document.
              if (docStr != {}): 
                 return dict(docStr)
              else:
                 raise INVALID_TOKEN("MALFORMED EXPRESSION(S)")
           else:
              raise ILLEGAL_STATEMENT(str(docStr))
        #Error handling
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
        except pp.ParseBaseException as e:
           print ("PARSE_EXCEPTION: " + "({0})".format(e))

#==============================================================================
#Default setup
#==============================================================================
import sys
if __name__ == '__main__':
        contents = sys.stdin.read()
        d= parse(contents)
        if (d.__class__.__name__ != "dict"):
           sys.exit(1)
        print d
