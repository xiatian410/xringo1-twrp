#include <cassert>
#include <climits>
#include "twrpminui/twrp_input.cpp"

int gr_fb_width() { return 1440; }
int gr_fb_height() { return 3200; }
GRRotation gr_get_rotation() { return GRRotation::NONE; }
int property_get(const char*, char* v, const char* fallback) { strcpy(v,fallback);return strlen(v); }
int vibrate(int) { return 0; }
int ev_init(ev_callback,bool) { return 0; }
void ev_exit() {}
int ev_get_input(int,uint32_t,input_event*) { return -1; }
int ev_wait(int) { return -1; }
void ev_dispatch() {}

static void emit(ev* d, uint16_t type,uint16_t code,int value) {
    input_event e{};e.type=type;e.code=code;e.value=value;mt_process_event(d,&e);
}
static ev device() {
    ev d{};d.mt_type_b=true;d.mt_p.xi.maximum=143999;d.mt_p.yi.maximum=319999;
    for(auto& slot:d.mt_slots)slot.tracking_id=-1;
    return d;
}
int main() {
    ev d=device();int x,y;
    // The historical dijun input range is 100 times the panel resolution.
    for(int rotation:{0,90,180,270}) {
        touch_rotation=rotation;
        const int corners[4][2]={{0,0},{143999,0},{0,319999},{143999,319999}};
        const int expected[4][4][2]={
            {{0,0},{1439,0},{0,3199},{1439,3199}},
            {{1439,0},{1439,3199},{0,0},{0,3199}},
            {{1439,3199},{0,3199},{1439,0},{0,0}},
            {{0,3199},{0,0},{1439,3199},{1439,0}}
        };
        for(int i=0;i<4;++i) {
            assert(mt_point_to_screen(&d,corners[i][0],corners[i][1],&x,&y));
            assert(x==expected[rotation/90][i][0] && y==expected[rotation/90][i][1]);
        }
        assert(!mt_point_to_screen(&d,INT_MAX,INT_MAX,&x,&y));
        assert(!mt_point_to_screen(&d,-1000,-1000,&x,&y));
    }
    touch_rotation=0;
    TWRPTouchPoint points[TWRP_MAX_TOUCH_EVENTS];
    emit(&d,EV_ABS,ABS_MT_SLOT,0);emit(&d,EV_ABS,ABS_MT_TRACKING_ID,2);
    // Selected points copied from the user's historical swipe trace.
    const int trace[][2]={{0xfb90,0x26cb4},{0xf8d4,0x263b8},{0xccb0,0x242e8},
                         {0x9344,0x21bd8},{0xbea0,0x2308c},{0x1223c,0x279fc}};
    for(const auto& p:trace) {
        emit(&d,EV_ABS,ABS_MT_POSITION_X,p[0]);emit(&d,EV_ABS,ABS_MT_POSITION_Y,p[1]);
        emit(&d,EV_SYN,SYN_REPORT,0);
        assert(twrp_input_take_touch_events(points,TWRP_MAX_TOUCH_EVENTS)==1);
        assert(points[0].pressed);
        assert(abs(points[0].x-p[0]/100)<=1 && abs(points[0].y-p[1]/100)<=1);
    }
    emit(&d,EV_ABS,ABS_MT_TRACKING_ID,-1);emit(&d,EV_SYN,SYN_REPORT,0);
    assert(twrp_input_take_touch_events(points,TWRP_MAX_TOUCH_EVENTS)==1 && !points[0].pressed);
    for(int slot=0;slot<10;++slot) {
        emit(&d,EV_ABS,ABS_MT_SLOT,slot);emit(&d,EV_ABS,ABS_MT_TRACKING_ID,slot+20);
        emit(&d,EV_ABS,ABS_MT_POSITION_X,slot*10000);emit(&d,EV_ABS,ABS_MT_POSITION_Y,slot*20000);
    }
    emit(&d,EV_SYN,SYN_REPORT,0);
    assert(twrp_input_take_touch_events(points,TWRP_MAX_TOUCH_EVENTS)==10);
    for(int slot=0;slot<10;++slot)assert(points[slot].id==slot && points[slot].pressed);
    for(int slot=0;slot<10;++slot) {
        emit(&d,EV_ABS,ABS_MT_SLOT,slot);emit(&d,EV_ABS,ABS_MT_TRACKING_ID,-1);
    }
    emit(&d,EV_SYN,SYN_REPORT,0);
    assert(twrp_input_take_touch_events(points,TWRP_MAX_TOUCH_EVENTS)==10);
    for(int i=0;i<10;++i)assert(!points[i].pressed);
    twrp_input_exit();
    puts("PASS: dijun 100x range, four rotations/corners, overflow/outside range, historical swipe samples, 10 contacts and releases");
}
