#include <parted/parted.h>

static long long
get_size(const char*size_str)
{
    long long rs = 0;
    long double ld = 0;
    size_t len = 0;
    if(size_str)
    {
        len = strlen(size_str);
        ld = strtold(size_str,NULL);
        rs = ld;
        if(size_str[len-1] == 'k' ||size_str[len-1] == 'K')
        {
            rs = ld * 1024L;
        }else if(size_str[len-1] == 'M' ||size_str[len-1] == 'm')
        {
            rs = ld * 1024L*1024L;
        }else if(size_str[len-1] == 'G' ||size_str[len-1] == 'g')
        {
            rs = ld * 1024L*1024L*1024L;
        }else if(size_str[len-1] == 'T' ||size_str[len-1] == 't')
        {
            rs = ld * 1024L*1024L*1024L*1024L;
        }
    }
    return rs;
}

static void
print_geom(PedGeometry *geom,const char *msg)
{
    fprintf(stderr,"%s:\n",msg);
    fprintf(stderr,"    start :%lld\n",geom->start);
    fprintf(stderr,"    length:%lld\n",geom->length);
    fprintf(stderr,"    end   :%lld\n\n",geom->end);
}

int main(int argc,char **argv)
{
    PedDevice       *device = NULL;
    PedDisk         *disk = NULL;
    PedPartition    *part = NULL;
    PedFileSystem   *fs = NULL;
    PedGeometry     geom = {0};
    PedGeometry     *_geom = NULL;
    char *t = NULL;
    int code = 0;
    ped_device_probe_all();
    do{
        device=ped_device_get_next(device);
        if(device == NULL)
        {
            break;
        }        
        disk = ped_disk_new(device);
        do{
            part = ped_disk_next_partition(disk,part);
            if(part == NULL)
            {
                break;
            }
            t = ped_partition_get_path(part);
            if(argc >1 && t && strcmp(t,argv[1]) == 0)
            {
                if(part->fs_type)
                {
                    geom = part->geom;
                    fs=ped_file_system_open(&geom);
                    if(argc>2 && argv[2] && fs && fs->geom)
                    {
                        long long size = get_size(argv[2]);
                        PedSector length = size / device->sector_size;
                        if(length > 0 && length <= part->geom.length)
                        {
                            _geom = ped_geometry_new(fs->geom->dev,fs->geom->start,length);
                        }
                    }
                    if(_geom == NULL)
                    {
                        _geom = ped_geometry_new(part->geom.dev,fs->geom->start,part->geom.length-fs->geom->start+part->geom.start);
                    }
                    fprintf(stderr,"Resize '%s'.\n",t);
                    print_geom(fs->geom,"old geometry");
                    print_geom(_geom,"new geometry");
#if 1
                    code = ped_file_system_resize(fs,_geom,NULL);
                    if(code)
                    {
                        ped_disk_commit(disk);
                    }
#endif
                    ped_file_system_close(fs);
                    ped_geometry_destroy(_geom);
                }
                break;
            }
            free(t);
        }while(1);
        if(fs)break;
    }while(1);
    ped_device_free_all();
    return ! code;
}
