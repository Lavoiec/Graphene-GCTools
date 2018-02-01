"""
The file that powers the GraphQL querying system.

The project principally employs the graphene_sqlalchemy package to
create rapid templates of classes using the SQLAlchemy models defined in models.py.
Every column defined in models.py is automatically ported over into the graphene SQLALchemyObjectType,
complete with resolve function. For example, because I defined name in the Users Table, the Users class
I define in this file will already have included the name column as a field that can be queried through GraphQL.
This saves a lot of time and code, and makes it so this file only contains the more complex resolvers.

In future development using something other than the elgg database, all of this will still be useful.

This project also employs the gcga.py to link up a Google Analytics API to pages. 
"""


import graphene
from graphene import relay
from graphene_sqlalchemy import SQLAlchemyObjectType, SQLAlchemyConnectionField
from sqlalchemy import *
from models import db_session, Users as UsersModel, Entities as EntitiesModel, Relationships as RelationshipsModel, Groups as GroupsModel
from models import ObjectsEntity as ObjectsEntityModel, Metadata as MetadataModel, Metastrings as MetastringsModel
from gcga import gcga
import code

class Page(graphene.Interface):
    """
    An interface that is attached to the Groups and Content
    SQLAlchemyObjectTypes. Because each group and each piece of content
    is their own respective page, they will all have a pageviews field.

    Placing this interface over those Classes allows them to query their pageviews
    using gcga.pa
    """
    # The pageviews integer that will be returned
    # Filterable by guid
    pageviews = graphene.Int(guid=graphene.Int())

    def resolve_pageviews(self, info, **args):
        """
        Uses the gcga class, and calls the
        content_views() function, which returns a list

        This assumes that we are only interested in the first
        item in the list. If there are no views for that period,
        the list will return empty
        """
        # Gets the guid from the class from which it is being called
        guid = str(self.guid)

        a = gcga()
        # Hidden from this is the default values for start_date and end_date
        # This section will need to be overhauled eventually, so this was for testing
        # purposes
        x = a.content_views(guid)['pageviews']

        # If the list is empty, just make the thing.
        # Else, return the first item (a strong assumption)
        if not x:
            x = 0
        else:
            x = x[0]
        return x


class EntityProperties(SQLAlchemyObjectType):
    """
    Imports the SQLAlchemy model we defined in models.py
    """
    class Meta:
        model = MetastringsModel
        interfaces = (relay.Node,)

class ObjectsEntity(SQLAlchemyObjectType):
    """
    Imports the SQLAlchemy model we defined in models.py
    """
    class Meta:
        model = ObjectsEntityModel
        interfaces = (relay.Node,)


class Colleague(SQLAlchemyObjectType):
    """
    Imports the SQLAlchemy model we defined in models.py

    Also adds bio, which gives a little redundancy.
    Will be cleaned later
    """
    class Meta:
        model = UsersModel
        interfaces = (relay.Node,)
    # There are very similar properties in a user profile, that are relatively complex
    # to query (hence why we didn't do it in models.py)
    # Skills, Education, and Work
    # Each of them occupies multiple fields in the Objects_Entity table
    # Because their queries only differ  by the integer we call, they're all
    # bunched up in the same query
    
    # A list that follows the ObjectsEntity model, queryable on the type of bio (spec)
    # and whether it contains a certain string inside or not
    bio = graphene.List(ObjectsEntity, spec=graphene.String(), contains = graphene.String())


    def resolve_bio(self, info, **args):
        """
        Calls an ObjectsEntity object and resolves to query
        the object

        As a later update, should make it
        its own object, to merge metadata properties 
        """
        bio_dict = {
            "work": 48642,
            "education": 63856,
            "skills": 730759
        }
        # Calls the arguments defined in the bio variable outside the
        # method
        bio_type = args.get("spec")
        contains = args.get("contains")

        # A N 0 0 B 1 S H way of asserting the type
        try:
            bio_int = bio_dict[bio_type]
        except KeyError:
            raise KeyError("This isn't a proper type")
            
        
        # Calls in the ObjectsEntity Query on which we will query
        objectsdata_query = ObjectsEntity.get_query(info)

        return objectsdata_query.filter(
            ObjectsEntityModel.guid.in_(

                select([MetastringsModel.string]).\
                where(
                    and_(
                        MetadataModel.entity_guid == self.guid,
                        MetadataModel.value_id == MetastringsModel.id,
                        MetadataModel.name_id == bio_int
                    )
                )
            )
    ).filter(ObjectsEntityModel.title.contains(contains) | ObjectsEntityModel.description.contains(contains)).all()

class Users(SQLAlchemyObjectType):
    """
    Imports the user table, and other important
    features about users.
    """

    class Meta:
        model = UsersModel
        interfaces = (relay.Node,)

    # The parameters we will look to resolve
    colleagues = graphene.List(Colleague)
    bio = graphene.List(ObjectsEntity, spec=graphene.String(), contains=graphene.String())

    def resolve_colleagues(self, info, **args):
        """
        Grabs all the colleagues of the user.

        SQL Query:

        SELECT ue.*
        FROM elggusers_entity ue, elggrelationships_entity r
        WHERE r.guid_one = [USER GUID]
        AND r.relationship = 'friend'


        With the caveat that ue.* returns only what is
        defined in the Users model in models.py
        """
        usersdata_query = Colleague.get_query(info)

        colleagues = usersdata_query.filter(UsersModel.guid.in_(
            select([RelationshipsModel.guid_two]).\
            where(
                and_(
                    RelationshipsModel.guid_one == self.guid,
                    RelationshipsModel.relationship == 'friend'
                )
            )
        )
        ).all()
        return colleagues

    def resolve_bio(self, info, **args):
        """
        As a later update, should make it
        its own object, to merge metadata properties 
        """
        bio_dict = {
            "work": 48642,
            "education": 63856,
            "skills": 730759
        }
        bio_type = args.get("spec")
        contains = args.get("contains")

        try:
            bio_int = bio_dict[bio_type]
        except KeyError:
            raise KeyError("This isn't a proper type")
            
        

        objectsdata_query = ObjectsEntity.get_query(info)


        
        return objectsdata_query.filter(
            ObjectsEntityModel.guid.in_(

                select([MetastringsModel.string]).\
                where(
                    and_(
                        MetadataModel.entity_guid == self.guid,
                        MetadataModel.value_id == MetastringsModel.id,
                        MetadataModel.name_id == bio_int
                    )
                )
            )
    ).filter(ObjectsEntityModel.title.contains(contains) |
            ObjectsEntityModel.description.contains(contains)
            ).all()

class Comment(SQLAlchemyObjectType):
    """
    Implementing the code necessary to add comments.

    Comments are their own class by virtue of how they're kept within the database.
    They also don't have all the features that a regular post would have (like tags, comments, etc.)

    Just an author
    """
    class Meta:
        model = ObjectsEntityModel
        interfaces = (relay.Node,)
    # Because we're letting the author be an entire user object,
    # we are calling a list to nest the author object in.
    # This allows for an obscene amount of customization
    author = graphene.List(Users)

    def resolve_author(self, info, **args):
        """
        SELECT ue.*
        FROM elggusers_entity ue, elggentities e
        WHERE e.guid = [USER GUID]

        Recall that because we are grabbing the GraphQL
        User class defined above, we are actually
        doing much more than just querying the table,
        we are getting access to all of the methods in the User
        Class 
        """
        return Users.get_query(info).filter(
               UsersModel.guid.in_(
                   select([EntitiesModel.owner_guid]).\
                   where(
                       EntitiesModel.guid == self.guid
                   )
               )).all()     

class Content(SQLAlchemyObjectType):
    """
    The most important object on the Tools.
    Without content, none of this is important.

    This is why it models after one of the biggest
    tables in elgg and links up to many tables
    """
    class Meta:
        model = EntitiesModel
        interfaces = (relay.Node, Page)

    author = graphene.List(Users)
    post = graphene.List(ObjectsEntity)
    comments = graphene.List(Comment)
    tags = graphene.List(EntityProperties)

    def resolve_author(self, info, **args):
        """
        SELECT ue.*
        FROM elggusers_entity ue, elggentities e
        WHERE e.guid = [USER GUID]

        Recall that because we are grabbing the GraphQL
        User class defined above, we are actually
        doing much more than just querying the table,
        we are getting access to all of the methods in the User
        Class 
        """
        return Users.get_query(info).filter(
               self.owner_guid == UsersModel.guid
               ).all()

    def resolve_post(self, info, **args):
        """
        Gets the actual post, which is broken
        into the title and description and stored in the
        elggobjects_entity table.


        SELECT oe.*
        FROM elggobjects_entity oe
        WHERE oe.guid = [CONTENT GUID] 
        """
        return ObjectsEntity.get_query(info).filter(
        self.guid == ObjectsEntityModel.guid)



    def resolve_comments(self, info, **args):
        """
        Grabs the Comments class we made above
        SELECT oe.*
        FROM elggobjects_entity oe, elggentities e
        WHERE e.container_guid = [CONTENT GUID]
        AND   e.subtype IN (64,66)

        Again, it calls the Comment class, so it has access
        to author, and therefore the User class as well.

        """
        # Calls in the comment query object
        comment_data = Comment.get_query(info)

        return comment_data.filter(
            ObjectsEntityModel.guid.in_(
            select([EntitiesModel.guid]).\
            where(
                and_(
                    EntitiesModel.container_guid == self.guid,
                    EntitiesModel.subtype.in_([64,66])
                )
            )
        )
    ).all()

    def resolve_tags(self, info, **args):
        """
        Calls the metastrings table, with the proper
        metadata code in order to extract tags

        SELECT ms.*
        FROM elggmetastrings ms, elggmetadata md
        WHERE ms.id = md.value_id
        AND md.name_id = 119
        AND md.entity_guid = [CONTENT GUID]
        """

        entity_data_model = EntityProperties.get_query(info)
        return entity_data_model.filter(
            MetastringsModel.id == MetadataModel.value_id,
            MetadataModel.name_id == 119,
            MetadataModel.entity_guid == self.guid
            ).all()
        
  
        return tags


class Entities(SQLAlchemyObjectType):
    """
    Importing the Entities Table
    """
    class Meta:
        model = EntitiesModel
        interfaces = (relay.Node,)

class Relationships(SQLAlchemyObjectType):
    """
    Importing the Relationships Table
    """
    class Meta:
        model = RelationshipsModel
        interfaces = (relay.Node,)

class Group(SQLAlchemyObjectType):
    """
    Importing the Groups table, which are basically
    giant incubators of activity. Users often create content within the
    groups, and the content resigns to a life of
    eternal captivity within it.
    (Documentation can go cheesily purple, right?)

    This class interfaces with the other two major types of elgg objects

    Missing tags and other metadata methods
    """
    class Meta:
        model = GroupsModel
        interfaces = (relay.Node, Page)
    # Members are important.
    members = graphene.List(Users)
    # Content is also important.
    content = graphene.List(Content, subtype=graphene.List(graphene.Int, default_value=[1,5,7,8,18,35,1,9]))

    def resolve_members(self, info, **args):
        """
        This query should be simple, but thanks to the
        arcane nature of elgg databases
        we must go through strange nesting

        SELECT ue.*
        FROM elggusers_entity ue
        WHERE ue.guid IN (
            SELECT r_prime.guid_one
            FROM elggentity_relationships r_prime
            WHERE r_prime.guid_two = [GROUP GUID]
            AND r_prime.relationship = 'member'
        )
        """
        return Users.get_query(info).filter(
                    UsersModel.guid.in_(
                        select([RelationshipsModel.guid_one]).\
                        where(
                            and_(
                            RelationshipsModel.guid_two == self.guid,
                            RelationshipsModel.relationship == 'member',
                        )))
                    ).all()

    def resolve_content(self, info, **args):
        """
        Content is also kept within a group.
        This grabs the content from the group, and allows
        the querier to filter on subtype


        SELECT e.*
        FROM elggentities e
        WHERE e.guid IN (
            SELECT e_prime.guid
            FROM elggentities e_prime
            WHERE e_prime.container_guid = [GROUP GUID]
            AND   e_prime.subtype IN  (SUBTYPE)
        )
        """
        subtype = args.get("subtype")
        
        return Content.get_query(info).filter(
                EntitiesModel.guid.in_(
                select([EntitiesModel.guid]).\
                where(
                    and_(
                        EntitiesModel.container_guid == self.guid,
                        EntitiesModel.subtype.in_(subtype)
            )
        )
    )
    ).all()


class Query(graphene.ObjectType):
    """
    Main query class. This is connected to the app.py
    file.

    Contains the main three pieces of the GCconnex database
    """
    nodes = relay.Node.Field()

    # Gathers all the users. Don't recommend
    all_users = SQLAlchemyConnectionField(Users)
    # Gathers all the entities. Do not do. This returns millions of things
    all_entities = SQLAlchemyConnectionField(Entities)
    user = graphene.List(Users, name=graphene.String())
    group = graphene.List(Group, guid=graphene.Int())
    content = graphene.List(Content, guid=graphene.Int())

    def resolve_user(self, info, **args):
        name = args.get("name")

        userdata_query = Users.get_query(info)

        users = userdata_query.filter(UsersModel.name.contains(name)).all()

        return users

    def resolve_group(self, info, **args):

        guid = args.get("guid")

        groupdata_query = Group.get_query(info)

        groups = groupdata_query.filter(GroupsModel.guid == guid).all()

        return groups

    def resolve_content(self, info, **args):

        guid = args.get("guid")

        return Content.get_query(info).filter(
                    guid == EntitiesModel.guid
            ).all()


        


schema = graphene.Schema(query=Query)