#每次新写完一个函数，就要在终端backend下执行python manage.py makemigrations 和 python manage.py migrate

from django.contrib import admin

from web.models.friend import Friend, Message
from web.models.user import UserProfile
from web.models.character import Character

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    raw_id_fields = ('user',) #逗号保留

@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    raw_id_fields = ('author',)

@admin.register(Friend)
class FriendAdmin(admin.ModelAdmin):
    raw_id_fields = ('me', 'character',)

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    raw_id_fields = ('friend',)