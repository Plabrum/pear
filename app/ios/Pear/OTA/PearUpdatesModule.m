#import <React/RCTBridgeModule.h>

@interface RCT_EXTERN_MODULE(PearUpdatesModule, NSObject)

RCT_EXTERN_METHOD(markBootSuccessful)

RCT_EXTERN_METHOD(getCurrentUpdateInfo
                   : (RCTPromiseResolveBlock)resolve reject
                   : (RCTPromiseRejectBlock)reject)

@end
