from django.shortcuts import render
from django.db.models import CharField,Q,Value
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminRole
from apps.core.pagination import StandardResultsPagination

# Create your views here.
class ReviewQueueView(APIView):
    permission_classes = [IsAuthenticated,IsAdminRole]

    def get(self,request):
        # imported here: this cross-content view depends on both apps
        from apps.blogs.models import Blog
        from apps.blogs.serializers import BlogSerializer
        from apps.videos.models import Video
        from apps.videos.serializers import VideoSerializer

        search = request.query_params.get('search','').strip()
        category_slug = request.query_params.get('category_slug','').strip()

        def pending(model):
            queryset = model.objects.visible_to(request.user).filter(status='pending')
            if search:
                queryset = queryset.filter(Q(title__icontains=search) | Q(contributor__name__icontains=search))
            if category_slug:
                queryset = queryset.filter(category__slug=category_slug)
            return queryset

        def rows(model,kind):
            return(
                pending(model)
                .order_by()
                .annotate(kind=Value(kind,output_field=CharField()))
                .values('id','submitted_at','kind')
            )

        merged = rows(Blog,'blog').union(rows(Video,'video')).order_by('submitted_at','id')

        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(merged,request,view=self)

        # load only this page's items in full
        blog_ids = [row['id'] for row in page if row['kind'] == 'blog']
        video_ids = [row['id'] for row in page if row['kind'] == 'video']

        blogs = {
            blog.id: blog
            for blog in Blog.objects.filter(id__in=blog_ids).select_related('contributor','category','cover_image')
        }

        videos = {
            video.id : video
            for video in Video.objects.filter(id__in=video_ids).select_related('contributor','category','thumbnail','media_asset')
        }

        context = {'request' : request}
        results = []
        for row in page:
            if row['kind'] == 'blog' and row['id'] in blogs:
                results.append({'kind':'blog','item':BlogSerializer(blogs[row['id']], context=context).data})
            elif row['kind'] == 'video' and row['id'] in videos:
                results.append({'kind':'video','item':VideoSerializer(videos[row['id']],context=context).data})

        return paginator.get_paginated_response(results)